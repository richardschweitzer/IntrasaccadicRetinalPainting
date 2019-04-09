#!/usr/bin/python

# --------------------------------------------------------------------------
# Presentation Interface for the DotStar Light Painter for Raspberry Pi.
#
# Hardware requirements:
# - Raspberry Pi computer (any model)
# - DotStar LED strip (any length, but 144 pixel/m is ideal)
# - One 74AHCT125 logic level shifter IC
# - High-current, high-capacity USB battery bank such as
#
# Software requirements:
# - Raspbian
# - Adafruit DotStar library for Raspberry Pi:
#   github.com/adafruit/Adafruit_DotStar_Pi
# - usbmount:
#   sudo apt-get install usbmount
#   See file "99_lightpaint_mount" for add'l info.
#
# Written by Phil Burgess / Paint Your Dragon for Adafruit Industries.
# Heavily modified by John Watson for Dr Tamara Watson
# --> This version is written by Richard Schweitzer for absolute timing and demo purposes!
#
# Adafruit invests time and resources providing this open source code,
# please support Adafruit and open-source hardware by purchasing products
# from Adafruit!
# --------------------------------------------------------------------------

## Libraries and prerequisites
import os
import sys
import select
import signal
import time
import RPi.GPIO as GPIO
import numpy as np
from dotstar import Adafruit_DotStar
from evdev import InputDevice, ecodes
from lightpaint import LightPaint
from PIL import Image
import npyscreen # sudo pip install npyscreen
import keyboard  # sudo pip install keyboard




## Setup Parameters
# specific setup and display options
n_strips = 4 ## the interface is for four LED strips!
pin_config = [[16, 26], [17, 27], [5, 6], [23, 24]] # [[datapin_1, clockpin_1], [datapin_2, clockpin_2], ...], SPI pins are: 10, 11
n_leds = [144, 144, 144, 144]
images = [["TestColourOrder.jpg", "TestColourOrder.jpg", "TestColourOrder.jpg", "TestColourOrder.jpg"], # 0
    ["WHY.png", "NOT.png", "CARE.png", "LESS.png"],     # 1
    ["ENJOY.png", "YOUR.png", "BEER.png", "MATE.png"],  # 2
    ["HER.png", "LOVE.png", "IS.png", "REAL.png"],      # 3
    ["CAN.png", "YOU.png", "SEE.png", "THIS.png"],      # 4
    ["VSS.png", "2019.png", "LOVES.png", "YOU.png"],    # 5
    ["LISA.png", "WON.png", "AN.png", "AWARD.png"],     # 6
    ["THE.png", "light.jpg", "IS.png", "NICE.png"],     # 7
    ["cactus.jpg", "usa.jpg", "30.jpg", "Donald-Trump.jpg"],  # 8: picture stimuli
    ["marge.jpg", "lisa.jpg", "bart.jpg", "homer.jpg"]]        # 9: picture stimuli
images_default = 0 #  "Check that each LED shows all three colours, Green, Red, Blue"
n_images = len(images)

# standard/start values
brightness_config = [255, 255, 255, 255]
display_durs = [25, 25, 25, 25] # in ms
inter_durs = [1, 1, 1, 1] # in ms
fix_time = 100 # how much time between iterations?
start_left = 1 # 1: left-to-right, 0: right-to-left presentation
presentation_alternating = 0 # 0: always in one direction, 1: alternating directions
    
# global settings
image_path = '/home/pi/PersistenceOfVision/pv/NEW PV/stimuli'
color_order = "bgr" # valid values  rgb, rbg, gbr, grb, brg, bgr, any 3 letter combination of rgb
vflip = 'true' # 'true' if strip input at bottom, else 'false'
gamma          = (2.8, 2.8, 2.8) # Gamma correction curves for R,G,B
color_balance_factors  = (0.5, 1, 0.75) # brightness multipliers for max brightness for R,G,B (white balance)
power_settings = (1450, 1550)    # Battery avg and peak current
hardware_spi_rate = 10000000    # rate of hardware SPI, if SPI pins are specified
max_dur_slider = 100            # slider maximum presentation duration
max_brightness_slider = 255     # slider maximum brightness
WaitForKey_time = 0.1      # in seconds, how much time for detecting a key?
increase_duration_step = 1  # in milliseconds


## Aux functions
# Load image, do some conversion and processing as needed before painting.
def loadImage(filename, strip, npixels, brightness, 
        gamma, color_balance_factors, power_settings, color_order, vflip):
    # Red = loading
    for n in range(npixels):
        strip.setPixelColor(n, 0x010000) 
        strip.show()
    # Load image, convert to RGB if needed
    img = Image.open(os.path.join(image_path, filename)).convert("RGB")
    imgwidth = img.size[0]
    # If necessary, image is vertically scaled to match LED strip.
    # Width is NOT resized, this is on purpose.
    if img.size[1] != npixels:
        img = img.resize((imgwidth, npixels), Image.BICUBIC)
    # Convert raw RGB pixel data to a string buffer.
    # The C module can easily work with this format.
    pixels = img.tostring()
    # Do external C processing on image; this provides 16-bit gamma
    # correction, diffusion dithering and brightness adjustment to
    # match power source capabilities.
    for n in range(npixels):
        strip.setPixelColor(n, 0x010100) # Yellow
        strip.show()
    # make color balance according to intended brightness
    color_balance = (int(round(brightness*color_balance_factors[0])),
        int(round(brightness*color_balance_factors[1])), 
        int(round(brightness*color_balance_factors[2])))
    # Pixel buffer, image size, gamma, color balance and power settings
    # are REQUIRED arguments.  One or two additional arguments may
    # optionally be specified:  "order='gbr'" changes the DotStar LED
    # color component order to be compatible with older strips (same
    # setting needs to be present in the Adafruit_DotStar declaration
    # near the top of this code).  "vflip='true'" indicates that the
    # input end of the strip is at the bottom, rather than top (I
    # prefer having the Pi at the bottom as it provides some weight).
    # Returns a LightPaint object which is used later for dithering
    # and display.
    lightpaint = LightPaint(pixels, img.size, gamma, color_balance,
        power_settings, order=color_order, vflip=vflip)
    # Success!
    for n in range(npixels):
        strip.setPixelColor(n, 0x000100) # Green
        strip.show()
    strip.clear()
    strip.show()
    # return the objects
    return lightpaint, imgwidth


def run_paint(dur, delay, lightpaint_name, ledBuffer, which_strip):
        elapsed = 0 # time elapsed since startTime
        frame_times = [] # here we'll list the timestamps
        startTime = time.clock() # time at start of the presentation 
        # interpolate through the frames
        if dur > 0:
            while elapsed <= dur:
                elapsed   = time.clock() - startTime
                lightpaint_name.dither(ledBuffer, elapsed / dur) # interpolate the column of the image write to buffer
                which_strip.show(ledBuffer) # display the buffer
                frame_times.append(time.clock() - startTime) # save the timestamp after the 'show' command
        else:
            print 'Warning! Duration is zero'
        # remove the display from the strip here
        which_strip.clear()
        which_strip.show()
        break_time = time.clock()
        frame_times.append(break_time-startTime) # last timestamp of presentation
        # wait for delay time (no need to timestamp this)
        sleep_for_time = delay+dur-(break_time-startTime)
        if sleep_for_time > 0:
            time.sleep(sleep_for_time)
        # return the number of frames and the timestamp
        return frame_times


def initialize_strips(n_leds_here, pin_config_here):
    strips_here = []
    # how many strips?
    n_strips_here = len(n_leds_here)
    # pin config complies with number of strips?
    assert(n_strips_here==len(pin_config_here))
    # start all strips
    for i in range(n_strips_here):
        print('Config of strip ' + str(i+1) + ': n_leds=' + str(n_leds_here[i]) + '; Data_pin=' + str(pin_config_here[i][0]) + '; Clock_pin=' + str(pin_config_here[i][1]))
        # initialize strip
        if pin_config[i][0]==10 & pin_config[i][1]==11: # hardware SPI pins
            strip = Adafruit_DotStar(n_leds[i], hardware_spi_rate, order=color_order)
        else: # other pins --> bit banging
            strip = Adafruit_DotStar(n_leds[i], pin_config[i][0], pin_config[i][1], order=color_order) 
        # start strip
        strip.begin()
        # add strip to list
        strips_here.append(strip)
    # return list of strips
    return strips_here


def set_brightness(strips_here, brightness_config_here):
    n_strips_here = len(strips_here)
    assert(n_strips_here == len(brightness_config_here))
    for i in range(n_strips_here):
        strips_here[i].begin()
        strips_here[i].setBrightness(brightness_config_here[i])
        print('--> brightness of strip ' + str(i+1) + ' set to: ' + str(brightness_config_here[i]))


def get_strip_buffer(strips_here):
    led_buffers_here = []
    n_strips_here = len(strips_here)
    for i in range(n_strips_here):
        # get buffer
        ledBuf = strips_here[i].getPixels() # Pointer to 'raw' LED strip data
        # add buffer to list
        led_buffers_here.append(ledBuf)
        # clear strip once...
        strips_here[i].clear()
        strips_here[i].show()
    # return list
    return led_buffers_here


def get_lightpaint(images_here, strips_here, n_leds_here, brightness_config_here):
    lightpaints_here = []; # lightpaint objects (have to load pictures in here)
    img_widths_here = [];  # widths of images (number of columns or "frames")
    # how many strips again?
    n_strips_here = len(strips_here)
    # make sure all configs have same length
    assert(n_strips_here==len(images_here))
    assert(n_strips_here==len(n_leds_here))
    assert(n_strips_here==len(brightness_config_here))
    # make lightpaint objects
    for i in range(n_strips_here):
        # 
        lightpaint, img_width = loadImage(images_here[i], strips_here[i], n_leds_here[i], brightness_config_here[i], 
            gamma, color_balance_factors, power_settings, color_order, vflip)
        # add to list
        lightpaints_here.append(lightpaint)
        img_widths_here.append(img_width)
        print('--> Loaded image of strip ' + str(i+1) + ': ' + images_here[i] + ' (brightness=' + str(brightness_config_here) + ')')
    return lightpaints_here, img_widths_here




## make form
class myPVoptions(npyscreen.Form):
    def afterEditing(self):
        self.parentApp.setNextForm(None)
    def create(self):
        # which test pattern to start?
        self.testPattern = self.add(npyscreen.TitleSlider, lowest = 0, out_of=n_images-1, 
            value = display_these_img,
            name = "Test pattern [0..9]")
        # presentation style
#        self.pres_style = self.add(npyscreen.TitleMultiSelect, max_height=-2, value = [1,], name="Pres style",
#            values = ["OneDirection", "Alternating"], scroll_exit=True)
#        self.start_left = self.add(npyscreen.TitleMultiSelect, max_height=-2, value = [1,], name="Start where",
#            values = ["left", "right"], scroll_exit=True)
        # presentation duration
        self.duration_1    = self.add(npyscreen.TitleSlider, lowest=1, out_of=max_dur_slider, 
            value = display_durs[0], 
            name = "Pres. Duration Strip 1 [ms]")
        self.duration_2    = self.add(npyscreen.TitleSlider, lowest=1, out_of=max_dur_slider, 
            value = display_durs[1], 
            name = "Pres. Duration Strip 2 [ms]")
        self.duration_3    = self.add(npyscreen.TitleSlider, lowest=1, out_of=max_dur_slider, 
            value = display_durs[2], 
            name = "Pres. Duration Strip 3 [ms]")
        self.duration_4    = self.add(npyscreen.TitleSlider, lowest=1, out_of=max_dur_slider, 
            value = display_durs[3], 
            name = "Pres. Duration Strip 4 [ms]")
        # inter-strip duration
        self.inter_duration_1    = self.add(npyscreen.TitleSlider, lowest=1, out_of=max_dur_slider, 
            value = inter_durs[0], 
            name = "Inter-duration Strip 1->2 [ms]")
        self.inter_duration_2    = self.add(npyscreen.TitleSlider, lowest=1, out_of=max_dur_slider, 
            value = inter_durs[1], 
            name = "Inter-duration Strip 2->3 [ms]")
        self.inter_duration_3    = self.add(npyscreen.TitleSlider, lowest=1, out_of=max_dur_slider, 
            value = inter_durs[2], 
            name = "Inter-duration Strip 3->4 [ms]")
        self.inter_duration_4    = self.add(npyscreen.TitleSlider, lowest=1, out_of=max_dur_slider, 
            value = inter_durs[3], 
            name = "Inter-duration Strip 4->1 [ms]")
        # brightness
        self.brightness_1    = self.add(npyscreen.TitleSlider, lowest=1, out_of=max_brightness_slider, 
            value = brightness_config[0], 
            name = "Brightness Strip 1 [1..255]")
        self.brightness_2    = self.add(npyscreen.TitleSlider, lowest=1, out_of=max_brightness_slider, 
            value = brightness_config[1], 
            name = "Brightness Strip 2 [1..255]")
        self.brightness_3    = self.add(npyscreen.TitleSlider, lowest=1, out_of=max_brightness_slider, 
            value = brightness_config[2], 
            name = "Brightness Strip 3 [1..255]")
        self.brightness_4    = self.add(npyscreen.TitleSlider, lowest=1, out_of=max_brightness_slider, 
            value = brightness_config[3], 
            name = "Brightness Strip 4 [1..255]")


def myPVinterface(*args):
    F = myPVoptions(name = 'Intra-saccadic Persistence of Vision Options')
    F.edit()
    # test pattern
    which_test_pattern = int(round(F.testPattern.value))
    # 
#    pres_style_here = F.pres_style.value
#    print(pres_style_here)
#    start_left_here = F.start_left.value
#    print(start_left_here)
    # presentation duration
    new_display_durs = []
    new_display_durs.append(int(round(F.duration_1.value)))
    new_display_durs.append(int(round(F.duration_2.value)))
    new_display_durs.append(int(round(F.duration_3.value)))
    new_display_durs.append(int(round(F.duration_4.value)))
    # inter-strip duration
    new_inter_durs = []
    new_inter_durs.append(int(round(F.inter_duration_1.value)))
    new_inter_durs.append(int(round(F.inter_duration_2.value)))
    new_inter_durs.append(int(round(F.inter_duration_3.value)))
    new_inter_durs.append(int(round(F.inter_duration_4.value)))
    # brightness
    new_brightness = []
    new_brightness.append(int(round(F.brightness_1.value)))
    new_brightness.append(int(round(F.brightness_2.value)))
    new_brightness.append(int(round(F.brightness_3.value)))
    new_brightness.append(int(round(F.brightness_4.value)))
    # return these
    return new_display_durs, new_inter_durs, new_brightness, which_test_pattern


def checkKeyboard(display_durs, inter_durs, brightness_config, not_pressed_ESC, display_these_img, lightpaints, img_widths):
    # will be set to True if lightpaint shall be switched
    switch_lightpaint = False 
    
    # check keyboard here
    try:  # used try so that if user pressed other than the given key error will not be shown
        # ESCAPE if key 'ESC' is pressed 
        if keyboard.is_pressed('ESC'):  
            not_pressed_ESC = False
        # enter options!
        elif keyboard.is_pressed('o'):
            # run the options interface!
            new_display_durs, new_inter_durs, new_brightness_config, new_test_pattern = npyscreen.wrapper_basic(myPVinterface)
            # update presentation durations                
            if not display_durs == new_display_durs: 
                print('New display durations = ' + str(new_display_durs))
                display_durs = new_display_durs
            # update inter-strips durations
            if not inter_durs == new_inter_durs: 
                print('New inter-strip durations = ' + str(new_inter_durs))
                inter_durs = new_inter_durs
            # update brightness config
            if not brightness_config == new_brightness_config: 
                print('New brightness configuration = ' + str(new_brightness_config))
                brightness_config = new_brightness_config
                set_brightness(strips, new_brightness_config) # set new brightness
                switch_lightpaint = True # also load the images once more with altered brightness
            # update what images to display
            if not new_test_pattern == display_these_img: 
                display_these_img = new_test_pattern
                switch_lightpaint = True
        # increase overall speed
        elif keyboard.is_pressed('up'): 
            if display_durs[0] < max_dur_slider:
                display_durs[0] += increase_duration_step
            if display_durs[1] < max_dur_slider:
                display_durs[1] += increase_duration_step
            if display_durs[2] < max_dur_slider:
                display_durs[2] += increase_duration_step
            if display_durs[3] < max_dur_slider:
                display_durs[3] += increase_duration_step
        # decrease overall speed
        elif keyboard.is_pressed('down'): 
            if display_durs[0] > 1:
                display_durs[0] -= increase_duration_step
            if display_durs[1] > 1:
                display_durs[1] -= increase_duration_step
            if display_durs[2] > 1:
                display_durs[2] -= increase_duration_step
            if display_durs[3] > 1:
                display_durs[3] -= increase_duration_step
        # switch to test pattern 0
        elif keyboard.is_pressed('0'): 
            display_these_img = 0
            switch_lightpaint = True
        # switch to test pattern 1
        elif keyboard.is_pressed('1'): 
            display_these_img = 1
            switch_lightpaint = True
        # switch to test pattern 2
        elif keyboard.is_pressed('2'): 
            display_these_img = 2
            switch_lightpaint = True
        # switch to test pattern 3
        elif keyboard.is_pressed('3'): 
            display_these_img = 3
            switch_lightpaint = True
        # switch to test pattern 4
        elif keyboard.is_pressed('4'): 
            display_these_img = 4
            switch_lightpaint = True
        # switch to test pattern 5
        elif keyboard.is_pressed('5'): 
            display_these_img = 5
            switch_lightpaint = True
        # switch to test pattern 6
        elif keyboard.is_pressed('6'): 
            display_these_img = 6
            switch_lightpaint = True
        # switch to test pattern 7
        elif keyboard.is_pressed('7'): 
            display_these_img = 7
            switch_lightpaint = True
        # switch to test pattern 8
        elif keyboard.is_pressed('8'): 
            display_these_img = 8
            switch_lightpaint = True
        # switch to test pattern 9
        elif keyboard.is_pressed('9'): 
            display_these_img = 9
            switch_lightpaint = True
        # do nothing if no key was pressed
        else:
            pass
    except:
        pass  # if user pressed a key other than the given key the loop will not break
    
    # if necessary, load new test patterns!
    if switch_lightpaint == True:
        print('Now display test pattern: ' + str(display_these_img))
        lightpaints, img_widths = get_lightpaint(images[display_these_img], strips, n_leds, brightness_config)
    
    # return here
    return display_durs, inter_durs, brightness_config, not_pressed_ESC, display_these_img, lightpaints, img_widths



## read new values
if __name__ == '__main__':
    
    ## Create and initialize strips
    # check consistency of inputs
    display_these_img = images_default
    assert(len(images[display_these_img])==len(display_durs))
    assert(len(display_durs)==len(inter_durs))
    assert(len(display_durs)==n_strips)

    # set up strip list
    strips = initialize_strips(n_leds, pin_config)

    # set brightness
    set_brightness(strips, brightness_config)

    # make LED buffers for strips
    led_buffers = get_strip_buffer(strips)

    # create lightpaint object, load image that we've specified
    lightpaints, img_widths = get_lightpaint(images[display_these_img], strips, n_leds, brightness_config)

    # okay!
    print('Done preparing!')
    

    ## Display and timing loop
    try:
        iteration_nr = 0
        # setup loop
        i = 0
        pres_durs = []        # what's the real presentation time?
        n_shows = []          # how many shows per strip?
        inter_frame_time = [] # what's the mean time between 'shows'
        not_pressed_ESC = True
        # run the presentation until we press a valid key
        while not_pressed_ESC:
            # run the presentation function
            if start_left == 1: # left-to-right presentation
                frame_times = run_paint(display_durs[i]/1000.0, inter_durs[i]/1000.0, 
                    lightpaints[i], led_buffers[i], strips[i])
            else: # right-to-left presentation
                frame_times = run_paint(display_durs[(n_strips-1)-i]/1000.0, inter_durs[(n_strips-1)-i]/1000.0, 
                    lightpaints[(n_strips-1)-i], led_buffers[(n_strips-1)-i], strips[(n_strips-1)-i])
            # save the timing info
            pres_durs.append(round(frame_times[-1]*1000,2))
            n_shows.append(len(frame_times)-1)
            inter_frame_time.append(round(np.mean(np.diff(frame_times[0:len(frame_times)-1]))*1000, 2))
            # check keyboard and update config, if necessary
            display_durs, inter_durs, brightness_config, not_pressed_ESC, display_these_img, lightpaints, img_widths = checkKeyboard(
                display_durs, inter_durs, brightness_config, not_pressed_ESC, display_these_img, lightpaints, img_widths)
            # iterate
            i += 1
            if i == n_strips:
                iteration_nr += 1     # how many iterations so far?
                # show some feedback
                print('Iter=' + str(iteration_nr) + ' Presentation duration: ' + str(pres_durs))
                print('Iter=' + str(iteration_nr) + ' Number of "shows":     ' + str(n_shows))
                print('Iter=' + str(iteration_nr) + ' Time between "shows":  ' + str(inter_frame_time))
                print(' ')
                # reset
                i = 0
                pres_durs = []        # what's the real presentation time?
                n_shows = []          # how many shows per strip?
                inter_frame_time = [] # what's the mean time between 'shows'
                # update left-to-right -> right-to-left and reverse
                if presentation_alternating == 1:
                    if start_left == 1:
                        start_left = 0
                    else:
                        start_left = 1
                # system sleep to prepare for presentation once more
                time.sleep(fix_time/1000.0)
            
    except KeyboardInterrupt:
        # all done.
        print('Exiting...')
        for i in range(n_strips):
            strips[i].clear()
            strips[i].show()
        sys.exit()
        
    ## Shutdown and save
    for i in range(n_strips):
        strips[i].clear()
        strips[i].show()
    sys.exit()



