'''
Bluetooth LE CTP500 thermal printer client by Mel at ThirtyThreeDown Studio
See https://thirtythreedown.com/2025/11/02/pc-app-for-walmart-thermal-printer/ for process and details!
Shout out to Bitflip, Tsathoggualware, Reid and all the mad lasses and lads whose research made this possible!

'''

#System imports
import socket
import sys
from time import sleep
import struct
import serial
import serial.tools.list_ports
import json
import argparse

#Tkinter imports
import tkinter as tk
from tkinter import Frame, Label, Button, Text, Radiobutton, messagebox
from tkinter.messagebox import showinfo
from tkinter import filedialog as fd
from tkinter import scrolledtext
from tkinter import ttk

#PILLOW imports
import PIL.Image
import PIL.ImageTk
import PIL.ImageDraw
import PIL.ImageFont
import PIL.ImageChops
import PIL.ImageOps
import PIL.ImageEnhance

# Check for command line arguments (web mode)
parser = argparse.ArgumentParser(description='CTP500 Thermal Printer Control')
parser.add_argument('--web-data', help='JSON file containing web print data')
parser.add_argument('--get-com-ports', action='store_true', help='Get list of available COM ports')
args = parser.parse_args()

def get_available_com_ports():
    """Get list of available COM ports"""
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]

#COMMUNICATION LOGIC STARTS HERE
com_port = "COM1" #Default COM port - will be selectable in UI

class PrinterConnect: #Starting a PrinterConnect class to keep track of connection status
    def __init__(self):
        self.serial_conn = None #Starting a disconnected serial connection
        self.connected = False #Setting socket status to False/disconnected

    def connect(self, com_port): #Setting up a connection function
        if self.connected: #Checking to see if the printer is already connected
            print("Already connected") #Warning user
            return True #Switching PrinterConnect connection status

        try: #Starting all the things to do to establish a connection
            self.serial_conn = serial.Serial(com_port, 9600, timeout=1) #Setting up serial connection at 9600 baud

            print("Getting printer status")
            status = self.get_printer_status() #Calling the get_printer_status() function and storing it in status variable
            print(f'Printer status: {status}') #Displaying status variable

            self.connected = True #Switching connection status for tracking
            print("Connection established")
            return True #Returning status

        except Exception as e: #Exception handling in case something goes wrong
            print(f'Connection error: {e}')
            messagebox.showerror("Connection Error", f'Failed to connect with printer: {e}')
            if self.serial_conn: #If the serial connection is present:
                self.serial_conn.close() #Closing the connection
                self.serial_conn = None #Clearing the serial connection references
            return False #Returning status

    def disconnect(self): #Function to disconnect the serial connection
        if not self.connected or not self.serial_conn: #First a status check to see if already disconnected
            print("Not connected") #Communication to user
            return #Calling it a day

        try:
            print("Disconnecting printer")
            print("Closing serial connection")

            self.serial_conn.close()

            print("Clearing serial connection references")
            self.serial_conn = None #Clearing serial connection refs
            self.connected = False #Switching connection status tracking
            print("Disconnected")

        except Exception as e:
            print(f'Disconnection error: {e}') #Exception warning
            if self.serial_conn: #In case of connection close failure, we close anyway
                self.serial_conn.close() #Closing serial connection
                self.serial_conn = None #Clearing the serial connection
            self.connected = False #Setting connection status to false


    def get_printer_status(self):
        if not self.serial_conn:
            raise Exception("Not connected")
        self.serial_conn.write(b"\x1e\x47\x03") #Hex code for status request
        return self.serial_conn.read(38) #Returning status request content


printer = PrinterConnect() #Creating a printer connection instance here. Having it *outside* of a function lets us run and monitor connection across global scope
printerWidth = 384  # For CPT500

# Check if getting COM ports
if args.get_com_ports:
    try:
        ports = get_available_com_ports()
        print(json.dumps({'ports': ports}))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({'ports': ['COM1', 'COM2', 'COM3', 'COM4', 'COM5']}))
        sys.exit(1)

# Check if running in web mode
if args.web_data:
    try:
        # Load web data
        with open(args.web_data, 'r') as f:
            web_data = json.load(f)

        action = web_data.get('action')
        com_port = web_data.get('com_port', 'COM3')

        # Connect to printer
        if not printer.connect(com_port):
            print("Failed to connect to printer")
            sys.exit(1)

        if action == 'print_text':
            # Process text printing
            text_content = web_data.get('text_content', '')
            font = web_data.get('font', 'arial.ttf')
            font_size = int(web_data.get('font_size', 28))
            bold = web_data.get('bold', 'false').lower() == 'true'
            italic = web_data.get('italic', 'false').lower() == 'true'
            strikethrough = web_data.get('strikethrough', 'false').lower() == 'true'

            # Update global text formatting options
            global text_font, text_size, text_bold, text_italic, text_strikethrough
            text_font = font
            text_size = font_size
            text_bold = bold
            text_italic = italic
            text_strikethrough = strikethrough

            img = create_text(text_content)

            # Print the text
            initializePrinter(printer.serial_conn)
            sleep(0.5)
            sendStartPrintSequence(printer.serial_conn)
            sleep(0.5)
            printImage(printer.serial_conn, img)
            sleep(0.5)
            # Add two blank lines before end sequence
            printer.serial_conn.write(b"\r\n\r\n")
            sleep(0.2)
            sendEndPrintSequence(printer.serial_conn)
            sleep(0.5)

            print("Text printed successfully")

        elif action == 'print_image':
            # Process image printing
            image_path = web_data.get('image_path', '')
            brightness = float(web_data.get('brightness', 1.0))

            # Load and process image
            global image_brightness
            image_brightness = brightness
            current_image = PIL.Image.open(image_path)
            apply_image_brightness()  # Apply brightness adjustment

            # Print the image
            initializePrinter(printer.serial_conn)
            sleep(0.5)
            sendStartPrintSequence(printer.serial_conn)
            sleep(0.5)
            printImage(printer.serial_conn, current_image)
            sleep(0.5)
            # Add two blank lines before end sequence
            printer.serial_conn.write(b"\r\n\r\n")
            sleep(0.2)
            sendEndPrintSequence(printer.serial_conn)
            sleep(0.5)

            print("Image printed successfully")

        # Disconnect
        printer.disconnect()
        sys.exit(0)

    except Exception as e:
        print(f"Web mode error: {e}")
        sys.exit(1)

#PRINTER COMMUNICATION LOGIC AND SETUP ENDS HERE

#IMAGE DATA STORAGE STARTS HERE
current_image = None #Variable to store full resolution image
original_image = None #Variable to store original image for brightness adjustments
image_thumbnail = None #Variable to store image thumbnail
image_preview = None #Variable to store image preview for PhotoImage and canvas
image_brightness = 1.0 #Brightness multiplier (1.0 = original, >1 = brighter, <1 = darker)
#IMAGE DATA STORAGE ENDS HERE

#TEXT FORMATTING OPTIONS STARTS HERE
text_font = "arial.ttf" #Default text font
text_size = 28 #Default text size
text_bold = False #Bold text option
text_italic = False #Italic text option
text_strikethrough = False #Strikethrough text option
#TEXT FORMATTING OPTIONS ENDS HERE

#TEXT FILE MANAGEMENT STARTS HERE
def selectTextFile():
    textFilePath = fd.askopenfilename(
        title = "Open a text file",
        initialdir = "/"
    )

    showinfo(
        title="Selected file: ",
        message = textFilePath
    )

#SOMETHING WEIRD IS HAPPENING HERE, FAILURE TO CAPTURE INPUT FIELD
    if textFilePath:
        try:
            with open(textFilePath, 'r', encoding='utf-8') as textFile: #Using the file path we got from the user to read the file
                textFileContent=textFile.read()
                textInputField.delete('1.0', tk.END) #Clearing previously typed content
                textInputField.insert(tk.END, textFileContent) #Inserting the text file content

            #Insert some sort of status bar system here? Success messages and exception messages
            #Status Bar stuff
        except Exception as e:
            print("Woops, something went wrong.")
#TEXT FILE MANAGEMENT ENDS HERE

#TEXT AND IMAGE INPUT RENDERING AND PRINTING STARTS HERE
def create_text(text):
    #Use global text formatting options
    global text_font, text_size, text_bold, text_italic, text_strikethrough

    #Tweak to be able to change font w/ system fonts
    img = PIL.Image.new('RGB', (printerWidth, 5000), color=(255, 255, 255)) #Defines an RGB image, width is printer width, height is 5000px, color is white

    # Determine font file based on style preferences
    font_file = text_font
    if text_bold and text_italic:
        # Try bold italic variants
        variants = [text_font.replace('.ttf', 'bi.ttf'), text_font.replace('.ttf', 'bd.ttf'),
                   text_font.replace('.ttf', 'i.ttf'), text_font]
    elif text_bold:
        # Try bold variants
        variants = [text_font.replace('.ttf', 'bd.ttf'), text_font.replace('.ttf', 'b.ttf'), text_font]
    elif text_italic:
        # Try italic variants
        variants = [text_font.replace('.ttf', 'i.ttf'), text_font.replace('.ttf', 'it.ttf'), text_font]
    else:
        variants = [text_font]

    # Try to load the appropriate font variant
    font = None
    for variant in variants:
        try:
            font = PIL.ImageFont.truetype(variant, text_size)
            break
        except OSError:
            continue

    if font is None:
        try:
            # Try common system fonts on Windows
            for system_font in ["arial.ttf", "calibri.ttf", "tahoma.ttf", "verdana.ttf"]:
                try:
                    font = PIL.ImageFont.truetype(system_font, text_size)
                    break
                except OSError:
                    continue
            else:
                # If no system fonts work, use PIL's default font
                font = PIL.ImageFont.load_default()
        except:
            # Final fallback to default font
            font = PIL.ImageFont.load_default()

    d = PIL.ImageDraw.Draw(img) #Creates the d image object using the parameters above

    # Process text with styling
    y_position = 0
    line_height = font.getbbox("A")[3] + 5  # Get line height with some padding

    for line in text.splitlines():
        wrapped_lines = get_wrapped_text(line, font, printerWidth)
        for wrapped_line in wrapped_lines.split('\n'):
            if wrapped_line.strip():  # Skip empty lines
                # Draw the text
                d.text((0, y_position), wrapped_line, fill=(0, 0, 0), font=font)

                # Apply strikethrough if enabled
                if text_strikethrough:
                    # Calculate strikethrough line position (middle of text)
                    bbox = font.getbbox(wrapped_line)
                    text_height = bbox[3] - bbox[1]
                    strike_y = y_position + text_height // 2
                    strike_width = font.getlength(wrapped_line)

                    # Draw strikethrough line
                    d.line([(0, strike_y), (strike_width, strike_y)], fill=(0, 0, 0), width=2)

                y_position += line_height

    return trimImage(img) #Trimming down the unused height of the d object using the trimImage() function above

def get_wrapped_text(text: str, font: PIL.ImageFont.ImageFont, line_length: int): #Function to wrap the text to printer paper width
    lines = [''] #Empty list to store the lines
    for word in text.split(): #Iterating through the split words composing a sentence
        line = f'{lines[-1]} {word}'.strip() #Composing a "candidate line" out of words, one word at a time
        if font.getlength(line) <= line_length: #If the pixel length of the line is shorter than the printer width...
            lines[-1] = line #...We keep doing that!
        else:
            lines.append(word) #...Otherwise we create a new line in the list of lines, and continue from the next word on.
    return '\n'.join(lines) #Done processing the text, returning the lines dictionary as a text with line returns!

def print_from_entry():
    txt = textInputField.get("1.0", tk.END).strip() # Grab the text from the scrolled‑text widget
    if not txt:
        messagebox.showwarning("No text", "Please type or load some text.")
        return

    img = create_text(txt) #Turning the text to image

    if printer.connected and printer.serial_conn: #Send the text to the printer over the printer serial connection (if connected)
        try:
            initializePrinter(printer.serial_conn) #Initializing printer
            sleep(0.5)
            sendStartPrintSequence(printer.serial_conn) #Starting up print sequence
            sleep(0.5)
            printImage(printer.serial_conn, img) #Passing data to print
            sleep(0.5)
            # Add two blank lines before end sequence
            printer.serial_conn.write(b"\r\n\r\n")
            sleep(0.2)
            sendEndPrintSequence(printer.serial_conn) #Sending end of print sequence
            sleep(0.5)
            #messagebox.showinfo("Success", "Printed successfully.") #Optional success message
        except Exception as e:
            messagebox.showerror("Printing error", str(e))
    else:
        messagebox.showwarning("Not connected",
                               "Please connect to the printer first.")

def print_from_image():
    """Send the currently loaded image to the printer."""
    if not current_image:
        messagebox.showwarning("No image", "Please load an image first.")
        return

    if not (printer.connected and printer.serial_conn):
        messagebox.showwarning("Not connected",
                               "Please connect to the printer first.")
        return

    try:
        print("Initializing printer")
        initializePrinter(printer.serial_conn)
        sleep(0.5)

        print("Starting print sequence")
        sendStartPrintSequence(printer.serial_conn)
        sleep(0.5)

        # THIS is where we actually hand the image over
        print("Printing image")
        printImage(printer.serial_conn, current_image)

        print("Adding blank lines")
        sleep(0.5)
        # Add two blank lines before end sequence
        printer.serial_conn.write(b"\r\n\r\n")
        sleep(0.2)

        print("Sending end sequence")
        sendEndPrintSequence(printer.serial_conn)
        sleep(0.5)

        messagebox.showinfo("Success", "Image printed successfully.")
    except Exception as e:
        messagebox.showerror("Printing error", str(e))


#IMAGE FILE SECTION STARTS HERE
def selectImageFile():
    global current_image, image_thumbnail, image_preview
    imageFilepath = fd.askopenfilename(
        title = "Open an image file",
        initialdir = "/",
        filetypes = (('PNG files', '*.png'), ('JPG files', '*.jpg'), ('jpeg files', '*.jpeg'), ('BMP files', '*.bmp'), ('SVG files', '*.svg'), ('all files', '*.*'))
        )

    showinfo(
        title="Selected file: ",
        message = imageFilepath
    )

#SOMETHING WEIRD IS HAPPENING HERE, FAILURE TO CAPTURE INPUT FIELD
    if imageFilepath:
        try:
            print("Opening image file")
            # Store original image for brightness adjustments
            global original_image
            original_image = PIL.Image.open(imageFilepath, 'r') #Storing the original image
            current_image = original_image.copy() #Make a copy to work with
            print(current_image)
            apply_image_brightness()  # Apply brightness adjustment to current_image

            image_thumbnail = current_image.copy() #Copying current_image into image_thumbnail
            print(image_thumbnail)
            image_thumbnail.thumbnail((300, 100)) #Resizing image_thumbail to canvas size (might not work)

            print("Generating preview")
            imageCanvas_width = imageCanvas.winfo_width() #Storing the width of the preview canvas
            imageCanvas_height = imageCanvas.winfo_height() #Storing the height of the preview canvas
            imageCanvas_x_center = imageCanvas_width//2 #Calculating x center of the preview canvas
            imageCanvas_y_center = imageCanvas_height//2 #Calculating y center of the preview canvas

            image_preview = PIL.ImageTk.PhotoImage(image_thumbnail) #Storing the thumbnail as a displayable object into image_preview
            imageCanvas.delete('all')  #Clearing any  previous image from the canvas display
            imageCanvas.create_image(imageCanvas_x_center, imageCanvas_y_center, anchor = "center", image=image_preview)  # Loading up the thumbnail into the center of the preview canvas

        except Exception as e:
            print("Woops, something went wrong.")
            print({e})

def apply_image_brightness():
    """Apply brightness adjustment to the current image"""
    global current_image, original_image, image_thumbnail, image_preview
    if original_image is None:
        return

    # Start with original image and apply brightness
    current_image = original_image.copy()
    enhancer = PIL.ImageEnhance.Brightness(current_image)
    current_image = enhancer.enhance(image_brightness)

    # Update thumbnail and preview if they exist
    if image_thumbnail is not None:
        image_thumbnail = current_image.copy()
        image_thumbnail.thumbnail((300, 100))

        if imageCanvas.winfo_exists():
            imageCanvas_width = imageCanvas.winfo_width()
            imageCanvas_height = imageCanvas.winfo_height()
            imageCanvas_x_center = imageCanvas_width//2
            imageCanvas_y_center = imageCanvas_height//2

            image_preview = PIL.ImageTk.PhotoImage(image_thumbnail)
            imageCanvas.delete('all')
            imageCanvas.create_image(imageCanvas_x_center, imageCanvas_y_center, anchor="center", image=image_preview)

def update_brightness(value):
    """Update brightness value and refresh image preview"""
    global image_brightness
    image_brightness = float(value)
    apply_image_brightness()

def update_text_font(value):
    """Update text font"""
    global text_font
    text_font = value

def update_text_size(value):
    """Update text size"""
    global text_size
    text_size = value

def update_text_style(style, value):
    """Update text style options"""
    global text_bold, text_italic, text_strikethrough
    if style == "bold":
        text_bold = value
    elif style == "italic":
        text_italic = value
    elif style == "strikethrough":
        text_strikethrough = value

#IMAGE FILE SECTION ENDS HERE

def printImage(serial_conn, im):
    if im.width > printerWidth:
        # Image is wider than printer resolution; scale it down proportionately
        height = int(im.height * (printerWidth / im.width))
        im = im.resize((printerWidth, height))

    if im.width < printerWidth:
        # Image is narrower than printer resolution; pad it out with white pixels
        padded_image = PIL.Image.new("1", (printerWidth, im.height), 1)
        padded_image.paste(im)
        im = padded_image

    #Add a function for text rotation
    # im = im.rotate(180)  # Print it so it looks right when spewing out of the mouth

    # If image is not 1-bit, convert it
    if im.mode != '1':
        im = im.convert('1')

    # If image width is not a multiple of 8 pixels, fix that
    if im.size[0] % 8:
        im2 = PIL.Image.new('1', (im.size[0] + 8 - im.size[0] % 8, im.size[1]), 'white')
        im2.paste(im, (0, 0))
        im = im2

    # Invert image, via greyscale for compatibility
    im = PIL.ImageOps.invert(im.convert('L'))
    # ... and now convert back to single bit
    im = im.convert('1')

    buf = b''.join((bytearray(b'\x1d\x76\x30\x00'),
                    struct.pack('2B', int(im.size[0] / 8 % 256),
                                int(im.size[0] / 8 / 256)),
                    struct.pack('2B', int(im.size[1] % 256),
                                int(im.size[1] / 256)),
                    im.tobytes()))

    serial_conn.write(buf)

def trimImage(im):
    bg = PIL.Image.new(im.mode, im.size, (255, 255, 255))
    diff = PIL.ImageChops.difference(im, bg)
    diff = PIL.ImageChops.add(diff, diff, 2.0)
    bbox = diff.getbbox()
    if bbox:
        return im.crop((bbox[0], bbox[1], bbox[2], bbox[3] + 10))  # Don't cut off the end of the image

def initializePrinter(soc):
    soc.write(b"\x1b\x40")

def sendStartPrintSequence(soc):
    #Check against hex dump
    soc.write(b"\x1d\x49\xf0\x19")

def sendEndPrintSequence(soc):
    #Check against hex dump. Missings \x9a?
    soc.write(b"\x0a\x0a\x0a\x9a")

#TEXT AND IMAGE INPUT RENDERING AND PRINTING ENDS HERE

#GUI SETUP STARTS HERE

root = tk.Tk()
frame = Frame(root)
frame.pack()

#Setting up window properties
root.title("CTP500 Printer Control")
root.configure() #Sets background color of the window. We will tweak this later to be able to select from printer colors and patterns
root.minsize(520, 750) #Sets min size of the window
root.geometry("520x750") #Changes original rendering position of the window

#CONNECTION TOOLS SECTION STARTS HERE
connectionFrame = Frame(root,
                       borderwidth=1,
                       padx=5,
                       pady=5)

connectionLabel = Label(connectionFrame, text = "Connection tools")
connectionLabel.pack(fill="x")

#COM Port selection
comPortLabel = Label(connectionFrame, text="COM Port:")
comPortLabel.pack(side="left", padx=(0, 5))

comPortVar = tk.StringVar()
comPortVar.set(com_port)  # Set default value

available_ports = get_available_com_ports()
if available_ports:
    comPortVar.set(available_ports[0])  # Set first available port as default

comPortCombo = ttk.Combobox(connectionFrame, textvariable=comPortVar, values=available_ports, width=10)
comPortCombo.pack(side="left", padx=(0, 10))

#Setting up connection button
connectButton = tk.Button(
    connectionFrame,
    text = "Connect",
    command=lambda: printer.connect(comPortVar.get()),
    padx = 15,
    pady = 15
).pack(
    side="left",
    expand=1
)

#Setting up disconnection button
disconnectButton = tk.Button(
    connectionFrame,
    text = "Disconnect",
    command=lambda: printer.disconnect(),
    padx = 15,
    pady = 15
).pack(
    side="left",
    expand=1
)

connectionFrame.pack() #Rendering connectionFrame
#CONNECTION TOOLS SECTION ENDS HERE

#TEXT TOOLS SECTION STARTS HERE
textFrame = Frame(root)
radioButtonsFrame = Frame(textFrame)

#Creating our list of justification options
justification_options = ["left",
                 "center",
                 "right"]
radioJustification_status = tk.IntVar() #Creating a watch state for the radio buttons for justification

textLabel = Label(textFrame, text="Text tools")
textLabel.pack(fill="x") #Text label for the text input section

for index in range(len(justification_options)): #Iterating through the list of justification options
    Radiobutton(radioButtonsFrame,
                text=justification_options[index],
                variable=radioJustification_status,
                value=index, padx=5).pack(side="left", expand=True) #Creating a button for each justification option

radioButtonsFrame.pack(fill="x", pady=(0, 5)) #Rendering the frame for the Justification radio buttons
#radioButtonsFrame.pack(fill="x", expand=1) #Rendering the frame for the Justification radio buttons

textInputField = scrolledtext.ScrolledText(textFrame, height=5, width=40) #Creating a text input widget to input text
textInputField.pack(fill="both") #Rendering the text input widget
textButton = Button(textFrame,
                    text="Select a text file",
                    padx=10, pady=15,
                    command=selectTextFile)
textButton.pack(expand=1, fill="x")

#Text formatting controls
formattingFrame = Frame(textFrame)
formattingFrame.pack(fill="x", pady=(5, 0))

#Font selection
fontLabel = Label(formattingFrame, text="Font:")
fontLabel.pack(side="left", padx=(0, 5))

fontVar = tk.StringVar()
fontVar.set(text_font)
fontCombo = ttk.Combobox(formattingFrame, textvariable=fontVar, width=15,
                        values=["arial.ttf", "calibri.ttf", "tahoma.ttf", "verdana.ttf", "times.ttf"])
fontCombo.bind("<<ComboboxSelected>>", lambda e: update_text_font(fontVar.get()))
fontCombo.pack(side="left", padx=(0, 10))

#Font size
sizeLabel = Label(formattingFrame, text="Size:")
sizeLabel.pack(side="left", padx=(0, 5))

sizeScale = tk.Scale(formattingFrame, from_=8, to=72, orient="horizontal", length=100,
                    command=lambda v: update_text_size(int(v)))
sizeScale.set(text_size)
sizeScale.pack(side="left", padx=(0, 10))

#Style checkboxes
styleLabel = Label(formattingFrame, text="Style:")
styleLabel.pack(side="left", padx=(0, 5))

boldVar = tk.BooleanVar(value=text_bold)
boldCheck = tk.Checkbutton(formattingFrame, text="Bold", variable=boldVar,
                          command=lambda: update_text_style("bold", boldVar.get()))
boldCheck.pack(side="left", padx=(0, 5))

italicVar = tk.BooleanVar(value=text_italic)
italicCheck = tk.Checkbutton(formattingFrame, text="Italic", variable=italicVar,
                            command=lambda: update_text_style("italic", italicVar.get()))
italicCheck.pack(side="left", padx=(0, 5))

strikethroughVar = tk.BooleanVar(value=text_strikethrough)
strikethroughCheck = tk.Checkbutton(formattingFrame, text="Strikethrough", variable=strikethroughVar,
                                   command=lambda: update_text_style("strikethrough", strikethroughVar.get()))
strikethroughCheck.pack(side="left")

textFrame.pack(fill="both") #Rendering the text input area frame

#Creating a frame for the Print Text button
# printTextFrame = Frame(textFrame)
printTextButton = Button(textFrame,
                         text="Print your text!",
                         padx=10, pady=15,
                         bg="green", fg="white",
                         command=print_from_entry)
printTextButton.pack(fill="x", pady=(5, 0))
# printTextFrame.pack(side="bottom", expand=1, fill="x")
#TEXT TOOLS SECTION ENDS HERE

#IMAGE TOOLS SECTION STARTS HERE
#Creating a frame for the image selection area
imageFrame = Frame(root)
imageLabel = Label(imageFrame, text="Image tools").pack(fill="x", pady=(0,5))

#Creating a canvas to display the image selection
imageCanvas = tk.Canvas(imageFrame,
                        width=300,
                        height=100,
                        bg = "white")
imageCanvas.pack(pady=(0,5)) #Rendering the image selection canvas

imageDisplay = Frame(imageFrame).pack(fill="both")  #Rendering the selected image to the image selection area

imageButton = Button(imageFrame,
                     text="Select an image file",
                     padx=10, pady=15,
                     command=selectImageFile)
imageButton.pack(fill="x")
#Displaying selected picture

#Brightness slider
brightnessFrame = Frame(imageFrame)
brightnessLabel = Label(brightnessFrame, text="Brightness:")
brightnessLabel.pack(side="left")

brightnessScale = tk.Scale(brightnessFrame, from_=0.1, to=3.0, resolution=0.1,
                          orient="horizontal", length=200,
                          command=lambda v: update_brightness(float(v)))
brightnessScale.set(image_brightness)
brightnessScale.pack(side="left", padx=(5, 0))
brightnessFrame.pack(pady=(5, 0))

#Creating a frame for the Print Image button
#printImageFrame = Frame(imageFrame)
printImageButton = Button(imageFrame,
                          text="Print your image!",
                          padx=10, pady=15,
                          bg="green", fg="white",
                          command=print_from_image)
printImageButton.pack(fill="x", pady=(5, 0))
imageFrame.pack(fill="both", expand=True, padx=10, pady=5)
#IMAGE TOOLS SECTION ENDS HERE

def on_closing(): #Cleanup operations when closing the window
    printer.disconnect() #Disconnecting the printer
    root.destroy() #Flushing the UI

root.protocol("WM_DELETE_WINDOW", on_closing) #Final window cleanup on app closing

root.mainloop() #If your mainloop() runs before your options, then nothing will show up. Keep that in mind!
