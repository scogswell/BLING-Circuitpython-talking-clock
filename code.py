# It's a BLING Talking Clock, but in CircuitPython.
# Steven Cogswell, February 2024.
#
# Tested under Circuitpython 9.x 
# Get your own BLING: https://unexpectedmaker.com/bling 
#
# To: install, copy all files to your CIRCUITPY drive on BLING
#     boot.py
#     code.py
#     font5x8.bin
#     secrets.py
#     /sd  
#
# These libraries should be in /lib:
#     adafruit_led_animation, adafruit_debouncer, adafruit_framebuf, adafruit_ntp, 
#     adafruit_pixel_framebuf, adafruit_requests, adafruit_ticks, 
#     foamyguy_nvm_helper (from community bundle) 
#
# Get library bundles from https://circuitpython.org/libraries  
#
# If the program complains it can't find board.I2S_AMP_BCLK you need a newer Circuitpython. 
#
#
# Set your wifi ssid and password in "secrets.py"
# Program will auto-attempt to set your time and timezone from the network.
#
# Copy the directory "voice" with all its files onto a FAT32 formatted microsd card
# and put it in the BLING microsd card slot.  These are the voice samples used for speaking.
# Replace the voice samples with your own cool voice samples for more fun and excitement.
#
# Directory /sd must exist in CIRCUITPY, even if you're not using an sd card.  It's the
# mount point for the sd card.
#
# Voice samples were generated using the TTS on Mac OSX, using included program for Mac OSX.
#
# You can put the voice directory on the BLING CIRCUITPY directory, just change the
# VOICE_DIR definition below.
#
# What the BLING buttons do:
# Button A: Speak the current time
# Button B: one short press, show message (demo)
# Button B: two short presses, show message (demo)
# Button B: long press, enter settings menu
# Button C: short press, print parameters to the serial port
# Button D: one short press, show message (demo)
# Button D: two short presses, show message (demo)
#
# In the settings menu:
# Button B: short press, advance to next menu option category
# Button C: short press, change option of current menu item (decrement)
# Button D: short press, change option of current menu item (increment)
# Button B: long press, exit and save settings.
#           special case, if "ERASE" is selected as "Y" then nvm settings will be erased
#           and defaults loaded.
#
# Settings stored in nvm should persist between power cycles:
# AMPM: Use AM/PM display format (Y) or 24hr format (N).  Affects both display and speaking
# COLOR: Color choices for display.  Edit the clock_colors[] in settings_menu() to add more
# SPEAK: if Y, announces the time at top of the hour (:00) and bottom of the hour (:30).
#        if N, does not.
#        Will always speak time for Button A short press regardless of this setting
# FLASH: if Y, the separator between the digits (default ":" will flash on and off)
#        if N, static display of separator
# ERASE: If Y, upon exiting settings nvm with all settings will be erased and defaults loaded
#        if N, no effect
#
# Most errors will display a terse message on BLING, and then a reboot countdown. Some errors
# (network, sd card, audio) are transitory and often just go away with a reboot because: computers.
#
import wifi
import board
import ssl
import socketpool
import digitalio
import neopixel
import os
import time
import adafruit_ticks
import microcontroller
from adafruit_pixel_framebuf import PixelFramebuffer
import adafruit_ntp
import rtc
from adafruit_debouncer import Button
import adafruit_requests
import audiobusio
import audiocore
import audiomixer
import storage
import sdcardio
import espidf
import foamyguy_nvm_helper as nvm_helper
import random

CLOCK_UPDATE = 250       # How often (ticks, like ms but ticks) to update the clock display.
BLING_BRIGHTNESS = 0.03  # BLING is so bright.  Do not burn your house down.
VOICE_DIR="/sd/voice/"   # Directory to look for voice files (sd card), must have trailing /
# VOICE_DIR="/voice/"    # Directory to look for voice files (on flash), must have trailing /
TOAST = 60 * 60 * 1000   # toast

class Settings:
    """
    Class to hold clock settings loaded from/saved to nvm
    """
    def __init__(self):
        self.use_am_pm = True
        self.speak = True
        self.color = 0x0000FF
        self.use_flashing_separator = True
        self.volume = 5
        self.load()

    def load(self):
        """
        load settings from nvm
        """
        print("Load settings from nvm")
        try:
            settings_nvm = nvm_helper.read_data()
            self.use_am_pm = settings_nvm['use_am_pm']
            self.speak = settings_nvm['speak']
            self.color = settings_nvm['color']
            self.use_flashing_separator = settings_nvm['use_flashing_separator']
            self.volume = settings_nvm['volume']
        except Exception as e:
            print(e)
            print("Error loading from nvm, using defaults")
            self.use_am_pm = True
            self.speak = True
            self.color = 0x0000FF
            self.use_flashing_separator = True
            self.volume = 5 
            self.save()
        self.print()

    def save(self):
        """
        Save settings to nvm
        """
        print("Save settings to nvm")
        self.print()
        nvm_helper.save_data(
            {
                "use_am_pm": self.use_am_pm,
                "speak": self.speak,
                "color": self.color,
                "use_flashing_separator": self.use_flashing_separator,
                "volume": self.volume
            }, test_run = False, verbose = True
        )

    def print(self):
        """
        Print out settings
        """
        print("use ampm is",self.use_am_pm)
        print("speaking time on :00 and :30 is",self.speak)
        print("color of clock is","0x{:06X}".format(self.color))
        print("flashing separator is",self.use_flashing_separator)

def get_external_ip():
    """
    Gets the network external IP address, used for get_utc_offset() to figure out the time zone automatically

    Based on https://github.com/UnexpectedMaker/bling/blob/main/firmware/Arduino/BLING_Talking_Clock/utc_offset.h
    Copyright (c) 2023 BitBank Software, Inc., written by Larry Bank
    """
    URL="http://api.ipify.org/?format=json"
    stream = requests.get(URL)
    json_response = stream.json()
    return json_response['ip']

def get_utc_offset():
    """
    Attempt to calculate the timezone based on the external IP address.

    Based on https://github.com/UnexpectedMaker/bling/blob/main/firmware/Arduino/BLING_Talking_Clock/utc_offset.h
    Copyright (c) 2023 BitBank Software, Inc., written by Larry Bank
    """
    IP = get_external_ip()
    URL="https://ipapi.co/{}/utc_offset/".format(IP)
    stream = requests.get(URL)
    tz = stream.text
    tz_hour = int(tz[0:3])
    tz_min = int(tz[3:5])
    tz_float = float(tz_hour+tz_min/60)
    print("tz",tz,"hour ",tz_hour, "minute",tz_min, "float", tz_float)
    return(tz_float)

def reboot_if_error(delay,predelay=1):
    """
    reboot the microcontroller after delay seconds delay

    :param delay: second to delay before rebooting
    :param predelay: seconds to wait before countdown (in case there's a message on the display to see first)
    """
    time.sleep(predelay)
    print("Reboot in",delay,"seconds")
    ticks_now=adafruit_ticks.ticks_ms()
    ticks_boot = adafruit_ticks.ticks_add(ticks_now,delay*1000)
    while (adafruit_ticks.ticks_less(adafruit_ticks.ticks_ms(),ticks_boot)):
        remaining=int(adafruit_ticks.ticks_diff(ticks_boot,adafruit_ticks.ticks_ms())/1000)
        bling_message("BOOT{:1}".format(remaining),x=0,y=0,color=0xFF0000)
        time.sleep(0.1)
    microcontroller.reset()
    # raise

def connect_wifi():
    """
    Setup WiFi connection using ssid/password from secrets
    """
    if wifi.radio.ipv4_address is not None:
        return
    try:
        bling_message("WiFi")
        print("Connecting to %s" % secrets['ssid'])
        wifi.radio.connect(secrets['ssid'],secrets['password'])
        print("Connected to %s!" % secrets['ssid'])
        print("IPv4 address",wifi.radio.ipv4_address)
    # Wi-Fi connectivity fails with error messages, not specific errors, so this except is broad.
    except Exception as e:  # pylint: disable=broad-except
        print(e)
        bling_message("Wifi?", color=0xFF0000)
        reboot_if_error(60)

def format_datetime(datetime):
    """
    Simple pretty-print for a datetime object

    :param datetime: A datetime object
    """
    # pylint: disable=consider-using-f-string
    return "{:02}:{:02}:{:02} ".format(
        datetime.tm_hour,
        datetime.tm_min,
        datetime.tm_sec,
    )

def bling_choice(text,y_or_n, x=0,y=0,color1=0xFFFFFF, x2=35,y2=0, color2=0x00FF00,font_name="font5x8.bin"):
    """
    Specific formatter for settings, shows text on left and Y/N choice on far right side.
    """
    BLING.fill(0x000000)
    BLING.text(text, x=x, y=y, color=color1, font_name=font_name,size=1)
    if y_or_n:
        BLING.text("Y",x=35,y=0, color=color2, font_name=font_name, size=1)
    else:
        BLING.text("N",x=x2,y=y2, color=color2, font_name=font_name, size=1)
    time.sleep(0.01)
    BLING.display()

def bling_message(text, x=0,y=0,color=0x0000FF,font_name="font5x8.bin"):
    """
    Display a message on BLING
    """
    BLING.fill(0x000000)
    BLING.text(text, x=x, y=y, color=color, font_name=font_name,size=1)
    time.sleep(0.01)
    BLING.display()

def bling_clear():
    """
    Clear the BLING screen
    """
    BLING.fill(0x000000)
    time.sleep(0.01)
    BLING.display()

def show_clock(t,digit_color=0x00FF00,separator_color=0xFFFFFF,separator_char=":", use_am_pm=True):
    """
    Display the current time on BLING.  options for am/pm or 24hr display, and flashing separator
    """
    BLING.fill(0x000000)
    if use_am_pm:
        if (t.tm_hour == 0):
            BLING.text("{:2}".format(12),x=0,y=0, color=digit_color)
        elif (t.tm_hour > 12):
            BLING.text("{:2}".format(t.tm_hour-12),x=0,y=0, color=digit_color)
        else:
            BLING.text("{:2}".format(t.tm_hour),x=0,y=0, color=digit_color)
    else:
        BLING.text("{:02}".format(t.tm_hour),x=0,y=0, color=digit_color)
    BLING.text(separator_char, x=10,y=0, color=separator_color)
    BLING.text("{:02}".format(t.tm_min), x=14,y=0, color=digit_color)
    if use_am_pm:
        if t.tm_hour >= 12:
            BLING.text("pm",x=28,y=0,color=digit_color)
        else:
            BLING.text("am",x=28,y=0,color=digit_color)
    else:
        BLING.text(separator_char, x=24,y=0, color=separator_color)
        BLING.text("{:02}".format(t.tm_sec), x=28,y=0,color=digit_color)
    BLING.display()

def speak_time(t, use_am_pm=True):
    """
    Speak the time.  Assembles speech from .wav files stored in directory DIR.
    Files are named <number>.wav e.g. - 45.wav says "forty five"
    The set has to have 0.wav to 59.wav
    Also files for am.wav and pm.wav
    0.wav says "oh" and not "zero" because whatever
    Use your own .wav files for fun and excitement.
    """
    files = []
    if use_am_pm and t.tm_hour > 12:
        files.append(str(t.tm_hour-12)+".wav")
    elif use_am_pm and t.tm_hour == 0:
        files.append("12.wav")
    elif not use_am_pm and t.tm_hour < 10:
        files.append("0.wav")
        files.append(str(t.tm_hour)+".wav")
    else:
        files.append(str(t.tm_hour)+".wav")
    if t.tm_min != 0:
        if t.tm_min < 10:
            files.append("0.wav")
        files.append(str(t.tm_min)+".wav")
    else:
        if use_am_pm == False:
            files.append("hundred.wav")
    if use_am_pm:
        if t.tm_hour >= 12:
            files.append("pm.wav")
        else:
            files.append("am.wav")
    # Speak the files in sequence
    for f in files:
        speak_single_file(f)

def speak_single_file(f, add_path=True):
    """
    Speak a single arbitrary file from the VOICE_DIR directory
    Normally will add VOICE_DIR (the sd card) to the path but
    you can select add_path=False and you supply the whole path.
    """
    if add_path:
        f_path = VOICE_DIR+f
    else:
        f_path = f
    print("Speaking",f_path)
    mixer.voice[0].level=bling_settings.volume/10.0
    try:
        with open(f_path,"rb") as wavfile:
            wav = audiocore.WaveFile(wavfile)
            mixer.voice[0].play(wav, loop=False)
            while(mixer.voice[0].playing):
                pass
            mixer.stop_voice(0)
    except Exception as e:
        print(e)
        print("Error during speaking")

def print_directory(path, tabs=0):
    """
    List files in a directory, for checking the SD card
    https://learn.adafruit.com/adafruit-microsd-spi-sdio/example-listing-files-on-sd-card

    """
    for file in os.listdir(path):
        stats = os.stat(path + "/" + file)
        filesize = stats[6]
        isdir = stats[0] & 0x4000

        if filesize < 1000:
            sizestr = str(filesize) + " by"
        elif filesize < 1000000:
            sizestr = "%0.1f KB" % (filesize / 1000)
        else:
            sizestr = "%0.1f MB" % (filesize / 1000000)

        prettyprintname = ""
        for _ in range(tabs):
            prettyprintname += "   "
        prettyprintname += file
        if isdir:
            prettyprintname += "/"
        print('{0:<40} Size: {1:>10}'.format(prettyprintname, sizestr))

        # recursively print directory contents
        if isdir:
            print_directory(path + "/" + file, tabs + 1)

def test_speak_time():
    """
    Routine to test the speak algorithm with various times, so you can test if the speaking
    algorithm is working to your taste. Doesn't get called in the main program normally
    """
    # Sequence of time info: (tm_year, tm_mon, tm_mday, tm_hour, tm_min, tm_sec, tm_wday, tm_yday, tm_isdst)
    #     tm_year: the year, 2017 for example
    #     tm_mon: the month, range [1, 12]
    #     tm_mday: the day of the month, range [1, 31]
    #     tm_hour: the hour, range [0, 23]
    #     tm_min: the minute, range [0, 59]
    #     tm_sec: the second, range [0, 61]
    #     tm_wday: the day of the week, range [0, 6], Monday is 0
    #     tm_yday: the day of the year, range [1, 366], -1 indicates not known
    #     tm_isdst: 1 when in daylight savings, 0 when not, -1 if unknown.
    x = time.struct_time((2024,1,28,11,00,13,6,-1,-1))
    speak_time(x, use_am_pm=bling_settings.use_am_pm)
    x = time.struct_time((2024,1,28,00,30,13,6,-1,-1))
    speak_time(x, use_am_pm=bling_settings.use_am_pm)
    x = time.struct_time((2024,1,28,00,00,13,6,-1,-1))
    speak_time(x, use_am_pm=bling_settings.use_am_pm)
    x = time.struct_time((2024,1,28,9,13,13,6,-1,-1))
    speak_time(x, use_am_pm=bling_settings.use_am_pm)
    x = time.struct_time((2024,1,28,19,45,13,6,-1,-1))
    speak_time(x, use_am_pm=bling_settings.use_am_pm)
    x = time.struct_time((2024,1,28,1,00,13,6,-1,-1))
    speak_time(x, use_am_pm=bling_settings.use_am_pm)

def erase_nvm():
    """
    Overwrite the nvm with bytes, effectively erasing any stored settings
    """
    microcontroller.nvm[0:256] = bytes(256)

def settings_menu():
    """
    Display and interact with a settings menu
    Special case if "ERASE" is selected with "Y" then nvm will be erased
      when exiting.
    Otherwise settings are saved to nvm when routine ends.
    """
    AMPM_OPTION="AMPM"
    COLOR_OPTION="COLOUR"  # Change this if it bothers you so much
    SPEAK_OPTION="SPEAK"
    FLASH_OPTION="FLASH"
    VOLUME_OPTION="VOL"
    ERASE_OPTION="ERASE"
    menu_items = [AMPM_OPTION, COLOR_OPTION, SPEAK_OPTION, VOLUME_OPTION, FLASH_OPTION, ERASE_OPTION]
    clock_colors = [0x0000FF, 0x00003F,
                    0x00FF00, 0x003F00,
                    0xFF0000, 0X3F0000,
                    0xFF00FF, 0x3F003F,
                    0x00FFFF, 0x003F3F,
                    0xFFFF00, 0x3F3F00,
                    0xFFFFFF, 0x3F3F3F]
    clock_color_index = clock_colors.index(bling_settings.color)
    menu_selection = 0
    erase_settings = False
    # initial choice on display
    bling_choice("AMPM",bling_settings.use_am_pm)

    while(True):
        BUTTON_A.update()
        BUTTON_B.update()
        BUTTON_C.update()
        BUTTON_D.update()
        # Short push of B: move to next menu item
        # Short push of C: change menu selection value
        # Short push of D: also change menu selection value, but in the other direction
        # Long push of B: save settings and exit (or erase nvm if ERASE Y is selected)
        if BUTTON_B.short_count == 1:
            menu_selection += 1
            if menu_selection > len(menu_items)-1:
                menu_selection=0
            if menu_items[menu_selection] == COLOR_OPTION:
                bling_message(menu_items[menu_selection],x=0,y=0,color=bling_settings.color)
            elif menu_items[menu_selection] == AMPM_OPTION:
                bling_choice(AMPM_OPTION,bling_settings.use_am_pm)
            elif menu_items[menu_selection] == SPEAK_OPTION:
                bling_choice(SPEAK_OPTION,bling_settings.speak)
            elif menu_items[menu_selection] == FLASH_OPTION:
                bling_choice(FLASH_OPTION,bling_settings.use_flashing_separator)
            elif menu_items[menu_selection] == ERASE_OPTION:
                bling_choice(ERASE_OPTION+"?", erase_settings)
            elif menu_items[menu_selection] == VOLUME_OPTION:
                bling_message(VOLUME_OPTION+" {:01}".format(bling_settings.volume))
        if BUTTON_C.short_count == 1:
            if menu_items[menu_selection] == COLOR_OPTION:
                clock_color_index -= 1
                if clock_color_index < 0:
                    clock_color_index = len(clock_colors)-1
                bling_settings.color = clock_colors[clock_color_index]
                bling_message(menu_items[menu_selection],x=0,y=0,color=bling_settings.color)
            if menu_items[menu_selection] == AMPM_OPTION:
                bling_settings.use_am_pm = not bling_settings.use_am_pm
                bling_choice(AMPM_OPTION,bling_settings.use_am_pm)
            if menu_items[menu_selection] == SPEAK_OPTION:
                bling_settings.speak = not bling_settings.speak
                bling_choice(SPEAK_OPTION,bling_settings.speak)
            if menu_items[menu_selection] == FLASH_OPTION:
                bling_settings.use_flashing_separator = not bling_settings.use_flashing_separator
                bling_choice(FLASH_OPTION,bling_settings.use_flashing_separator)
            if menu_items[menu_selection] == ERASE_OPTION:
                erase_settings = not erase_settings
                bling_choice(ERASE_OPTION+"?", erase_settings)
            if menu_items[menu_selection] == VOLUME_OPTION:
                bling_settings.volume -= 1
                if bling_settings.volume < 1:
                    bling_settings.volume=1
                bling_message(VOLUME_OPTION+" {:01}".format(bling_settings.volume))
                speak_single_file("bling.wav")
        if BUTTON_D.short_count == 1:
            if menu_items[menu_selection] == COLOR_OPTION:
                clock_color_index += 1
                if clock_color_index > len(clock_colors)-1:
                    clock_color_index = 0
                bling_settings.color = clock_colors[clock_color_index]
                bling_message(menu_items[menu_selection],x=0,y=0,color=bling_settings.color)
            if menu_items[menu_selection] == AMPM_OPTION:
                bling_settings.use_am_pm = not bling_settings.use_am_pm
                bling_choice(AMPM_OPTION,bling_settings.use_am_pm)
            if menu_items[menu_selection] == SPEAK_OPTION:
                bling_settings.speak = not bling_settings.speak
                bling_choice(SPEAK_OPTION,bling_settings.speak)
            if menu_items[menu_selection] == FLASH_OPTION:
                bling_settings.use_flashing_separator = not bling_settings.use_flashing_separator
                bling_choice(FLASH_OPTION,bling_settings.use_flashing_separator)
            if menu_items[menu_selection] == ERASE_OPTION:
                erase_settings = not erase_settings
                bling_choice(ERASE_OPTION+"?", erase_settings)
            if menu_items[menu_selection] == VOLUME_OPTION:
                bling_settings.volume += 1
                if bling_settings.volume > 10:
                    bling_settings.volume=10
                bling_message(VOLUME_OPTION+" {:01}".format(bling_settings.volume))
                speak_single_file("bling.wav")

        if BUTTON_B.long_press:
            if erase_settings:
                erase_nvm()
                bling_message("ERASED!",x=0,y=0,color=0xFF0000)
                reboot_if_error(5,predelay=2)
            else:
                bling_settings.save()
                bling_message("SAVED",x=0,y=0,color=0x00FF00)
                time.sleep(1)
            return

# Enable power to BLING pixel display
bling_power = digitalio.DigitalInOut(board.MATRIX_POWER)
bling_power.switch_to_output()
bling_power.value=True

# Setup BLING neopixel and PixelFrameBuffer objects
bling_pixel_width = 40
bling_pixel_height = 8
bling_num_pixels = bling_pixel_width * bling_pixel_height
BLING_raw = neopixel.NeoPixel(board.MATRIX_DATA,bling_num_pixels,brightness=BLING_BRIGHTNESS,auto_write=False)

# Framebuffer lets us use grids and fonts.
BLING = PixelFramebuffer(
    pixels=BLING_raw,
    width=bling_pixel_width,
    height=bling_pixel_height,
    alternating=False,
    rotation=2
)

bling_clear()

# Load settinsg from nvm
bling_settings = Settings()

# Setup debounced buttons
BUTTON_A_raw = digitalio.DigitalInOut(board.BUTTON_A)
BUTTON_A_raw.switch_to_input()
BUTTON_A = Button(BUTTON_A_raw, value_when_pressed=True, long_duration_ms=1000)

BUTTON_B_raw = digitalio.DigitalInOut(board.BUTTON_B)
BUTTON_B_raw.switch_to_input()
BUTTON_B = Button(BUTTON_B_raw, value_when_pressed=True, long_duration_ms=1000)

BUTTON_C_raw = digitalio.DigitalInOut(board.BUTTON_C)
BUTTON_C_raw.switch_to_input()
BUTTON_C = Button(BUTTON_C_raw, value_when_pressed=True, long_duration_ms=1000)

BUTTON_D_raw = digitalio.DigitalInOut(board.BUTTON_D)
BUTTON_D_raw.switch_to_input()
BUTTON_D = Button(BUTTON_D_raw, value_when_pressed=True, long_duration_ms=1000)

# Setup i2s audio output
try:
    audio = audiobusio.I2SOut(bit_clock=board.I2S_AMP_BCLK, word_select=board.I2S_AMP_LRCLK, data=board.I2S_AMP_DATA)
    mixer = audiomixer.Mixer(voice_count=1, sample_rate=22050, channel_count=1,
                         bits_per_sample=16, samples_signed=True)
    audio.play(mixer) # attach mixer to audio playback
except Exception as e:
    print(e)
    bling_message("audio?")
    reboot_if_error(60,predelay=2)

# Open up the SD card.  If there's an error opening it display an error on BLING
if VOICE_DIR.startswith("/sd"):
    try:
        sd_spi = board.SPI()
        sdcard = sdcardio.SDCard(sd_spi,board.SD_CS)
        vfs = storage.VfsFat(sdcard)
        if not 'sd' in os.listdir('/'):
            os.mkdir('/sd')
        storage.mount(vfs, "/sd")
    except Exception as e:
        print(e)
        bling_message("sdcard?")
        reboot_if_error(60,predelay=2)
# It's not fatal if the voice directory doesn't exist, it just won't speak anything
# but at least give a brief alert 
try:
    print("Checking voice directory",VOICE_DIR) 
    status = os.stat(VOICE_DIR[:-1])   # no trailing "/" on directory for os.stat()
    print(VOICE_DIR,"exists")
except OSError as e:
    print(e)
    print(VOICE_DIR,"does not exist")
    bling_message("NoVoice",x=0,y=0,color=0xFF0000)
    time.sleep(2)

# Get WiFi Parameters and connect
try:
    from secrets import secrets
except ImportError:
    print("WiFi credentials are kept in secrets.py - please add them there!")
    bling_message("secret?", color=0xFF0000)
    raise
connect_wifi()
time.sleep(0.5)

pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())

# Get the time and timezone
bling_message("tzone")
try:
    tz_offset=get_utc_offset()
except Exception as e:
    print(e)
    bling_message("tzone?")
    reboot_if_error(60,predelay=2)

bling_message("time")
try:
    ntp = adafruit_ntp.NTP(pool, tz_offset=tz_offset)
    rtc.RTC().datetime = ntp.datetime      # the ESP32S3 rtc, not the BLING RV3028C7
except Exception as e:
    print(e)
    bling_message("NTP?", color=0xFF0000)
    reboot_if_error(60,predelay=2)
print("current time:", format_datetime(time.localtime()))

bling_clear()

# Setup the update interval for the clock display
ticks_last_clock = adafruit_ticks.ticks_add(adafruit_ticks.ticks_ms(),-5000)
toast_window = adafruit_ticks.ticks_add(adafruit_ticks.ticks_ms(), TOAST)
clock_show_separator = True  # Show the separator between clock digits, alternates 
bling_message("BLING",x=5,y=0,color=0x00FF00)
speak_single_file("bling.wav")

# and we're off
while(True):
    BUTTON_A.update()   # debouncers need regular updates
    BUTTON_B.update()
    BUTTON_C.update()
    BUTTON_D.update()

    # Fun with buttons demo.
    # Button B long press: enter menu setup
    # Button C short press: print parameters to serial output
    # also demonstratea double clicking
    if BUTTON_A.short_count == 1:
        print("Button A pressed")
        print("Speaking time {}".format(format_datetime(t)))
        speak_time(time.localtime(), use_am_pm=bling_settings.use_am_pm)
    if BUTTON_B.short_count == 1:
        print("Button B pressed")
        bling_message("Butn B")
        time.sleep(0.5)
        bling_clear()
    if BUTTON_B.short_count == 2:
        print("Button B double-clicked")
        bling_message("Dbl B")
        time.sleep(0.5)
        bling_clear()
    if BUTTON_B.long_press:
        settings_menu()
    if BUTTON_C.short_count == 1:
        print("Button C pressed")
        bling_message("Butn C")
        bling_settings.print()
        print("total psram:",espidf.get_total_psram())
        print("Heap free size", espidf.heap_caps_get_free_size())
        print("Heap largest free block",espidf.heap_caps_get_largest_free_block())
        print("Heap total size",espidf.heap_caps_get_total_size())
        time.sleep(0.5)
        bling_clear()
    if BUTTON_D.short_count == 1:
        print("Button D pressed")
        bling_message("Butn D")
        time.sleep(0.5)
        bling_clear()
    if BUTTON_D.short_count == 2:
        print("Button D double-clicked")
        bling_message("Dbl D")
        time.sleep(0.5)
        bling_clear()

    # Only update the clock occasionally. We do the "speak" test inside this so we're guaranteed
    # the clock is updated before it speaks (prevents cases of clock displaying "7:59" and the speak
    # saying "8:00")
    if (adafruit_ticks.ticks_less(ticks_last_clock, adafruit_ticks.ticks_ms())):
        t=time.localtime()

        if (clock_show_separator == True):
            show_clock(t=t, digit_color=bling_settings.color, separator_char=":", separator_color=0x555555,use_am_pm=bling_settings.use_am_pm)
        elif bling_settings.use_flashing_separator:
            show_clock(t=t, digit_color=bling_settings.color, separator_char=" ", use_am_pm=bling_settings.use_am_pm)
        ticks_last_clock = adafruit_ticks.ticks_add(adafruit_ticks.ticks_ms(),CLOCK_UPDATE)
        clock_show_separator= not clock_show_separator

        # Speak the time if top of the hour
        if (t.tm_min==0 and t.tm_sec==0):
            if bling_settings.speak:
                print("Speaking time :00 {}".format(format_datetime(t)))
                speak_time(t, use_am_pm=bling_settings.use_am_pm)

        # Speak the time at the bottom of the hour
        if (t.tm_min==30 and t.tm_sec==0):
            if bling_settings.speak:
                print("Speaking time :30 {}".format(format_datetime(t)))
                speak_time(t, use_am_pm=bling_settings.use_am_pm)

        if (adafruit_ticks.ticks_less(toast_window,adafruit_ticks.ticks_ms())):
            print("Time for toast?")
            if random.random() < 0.01:
                bling_message("TOAST?",color=0x00FF00)
                print("Would anyone like any toast")
                if bling_settings.speak:
                    speak_single_file("toast.wav")
                time.sleep(3)
                toast_window = adafruit_ticks.ticks_add(adafruit_ticks.ticks_ms(),TOAST) # no toast again for a while
            else:
                toast_window = adafruit_ticks.ticks_add(adafruit_ticks.ticks_ms(),5*60*1000) # at least five minutes before checking again
