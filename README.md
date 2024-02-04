# It's a BLING Talking Clock, but in CircuitPython.

Tested under Circuitpython 9.x 

Get your own BLING: https://unexpectedmaker.com/bling 

To: install, copy all files to your CIRCUITPY drive on BLING
* `boot.py`
* `code.py`
* `font5x8.bin`
* `secrets.py`
* `/sd`  

These libraries should be in /lib:
    `adafruit_led_animation`, `adafruit_debouncer`, `adafruit_framebuf`, `adafruit_ntp`, 
    `adafruit_pixel_framebuf`, `adafruit_requests`, `adafruit_ticks`, 
    `foamyguy_nvm_helper` (from community bundle) 

Get library bundles from https://circuitpython.org/libraries  

If the program complains it can't find `board.I2S_AMP_BCLK` you need a newer Circuitpython. 

Set your wifi ssid and password in "secrets.py"
Program will auto-attempt to set your time and timezone from the network.

Copy the directory `voice` with all its files onto a FAT32 formatted microsd card
and put it in the BLING microsd card slot.  These are the voice samples used for speaking.
Replace the voice samples with your own cool voice samples for more fun and excitement.

Directory `/sd` must exist in CIRCUITPY, even if you're not using an sd card.  It's the
mount point for the sd card.

Voice samples were generated using the TTS on Mac OSX, using included program `makevoice.sh` for Mac OSX.

You can put the voice directory on the BLING CIRCUITPY directory, just change the
`VOICE_DIR` definition below.

What the BLING buttons do:
* Button A: Speak the current time
* Button B: one short press, show message (demo)
* Button B: two short presses, show message (demo)
* Button B: long press, enter settings menu
* Button C: short press, print parameters to the serial port
* Button D: one short press, show message (demo)
* Button D: two short presses, show message (demo)

In the settings menu:
* Button B: short press, advance to next menu option category
* Button C: short press, change option of current menu item (decrement)
* Button D: short press, change option of current menu item (increment)
* Button B: long press, exit and save settings.
          special case, if "ERASE" is selected as "Y" then nvm settings will be erased
          and defaults loaded.

Settings stored in nvm should persist between power cycles:
* AMPM: Use AM/PM display format (Y) or 24hr format (N).  Affects both display and speaking
* COLOR: Color choices for display.  Edit the clock_colors[] in settings_menu() to add more
* SPEAK: if Y, announces the time at top of the hour (:00) and bottom of the hour (:30).
       if N, does not.
       Will always speak time for Button A short press regardless of this setting
* FLASH: if Y, the separator between the digits (default ":" will flash on and off)
       if N, static display of separator
* ERASE: If Y, upon exiting settings nvm with all settings will be erased and defaults loaded
       if N, no effect

Most errors will display a terse message on BLING, and then a reboot countdown. Some errors
(network, sd card, audio) are transitory and often just go away with a reboot because: computers.
