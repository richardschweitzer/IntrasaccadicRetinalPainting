#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 11 20:06:53 2019

@author: richard
"""

from PIL import Image, ImageFont, ImageDraw
from numpy import random

# helper function to convert rgb-strings like '(255,255,0)' to tuples
def str_to_rgb(s):
    l_s = len(s)
    s2 = s[1:l_s-1]
    list_s2 = s2.split(',')
    res = [int(i) for i in list_s2]
    return res


# parameters
txt = 'LESS'
do_flip_txt = True
do_multiline = True
current_path = '/home/richard/Dropbox/PROMOTION WORKING FOLDER/Projects/Persistence of Vision/NEW PV/python text renderer/'
result_path = '/home/richard/Dropbox/PROMOTION WORKING FOLDER/Projects/Persistence of Vision/NEW PV/stimuli/'
image_size_x = 45
image_size_y = 144
x_offset = 30
y_offset = 0
image_scale_fac = 5
background_color =  (0, 0, 0)
do_randomize_foreground_color = True
foreground_color = (255, 255, 255)
fontsize = 35
font_ttf = "Helvetica-Regular.ttf" # "HUScalaBold.ttf"

# read list of colors
if do_randomize_foreground_color == True:
    import pandas as pd 
    myColors = pd.read_csv(current_path + 'list_of_rgb_colors.csv', sep=',', names = ['name', 'hex', 'rgb'])
    color_list = [str_to_rgb(i) for i in list(myColors['rgb'])]
    foreground_color = tuple(color_list[random.choice(range(len(color_list)))])


# make picture object and select font
tmp_image_size_x = image_scale_fac*image_size_x
tmp_image_size_y = image_scale_fac*image_size_y
image = Image.new("RGBA", (tmp_image_size_x, tmp_image_size_y), background_color)
draw = ImageDraw.Draw(image)
usr_font = ImageFont.truetype(current_path + 'fonts/' + font_ttf, fontsize*image_scale_fac)

# draw text vertically
len_txt = len(txt)
if do_multiline == True: # multiline drawing using multiline_text
    txt_new = ''
    for c in range(len_txt):
        txt_new = txt_new + txt[c] + '\n'        
    draw.multiline_text((x_offset+tmp_image_size_x/(2*image_scale_fac), y_offset+(tmp_image_size_y/(len_txt*len_txt))), 
                    txt_new, foreground_color,
                    font=usr_font, spacing = ((tmp_image_size_y/(len_txt*len_txt))-y_offset)/2.0, align="center")
else: # single lines with vertical offset
    for c in range(len_txt):
        draw.text((x_offset+tmp_image_size_x/(2*image_scale_fac), y_offset+c*(tmp_image_size_y/len_txt)), 
                  txt[c], foreground_color, font=usr_font)




# flip, if necessary
if do_flip_txt == True:
    image = image.transpose(Image.FLIP_LEFT_RIGHT)

# downscale image
img_resized = image.resize((image_size_x, image_size_y), Image.ANTIALIAS)

# save
img_resized.save(result_path + txt + '.png')
img_resized.show()
