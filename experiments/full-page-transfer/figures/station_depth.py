"""Render the historic crop and the independently registered depths for stations 49 and 49A."""

from pathlib import Path
import os
from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = Path(__file__).resolve().parent
W = 800
img = Image.new("RGB",(W,640),"#f8f6ee")
draw = ImageDraw.Draw(img)
ink, muted = "#153f47", "#45606a"


def font(size, family="regular"):
    names = {"regular":("Arial.ttf","DejaVuSans.ttf"), "bold":("Arial Bold.ttf","DejaVuSans-Bold.ttf"),
             "serif":("Georgia.ttf","DejaVuSerif.ttf")}
    for base in [Path(os.environ.get("FIGURE_FONTS",".")),Path("/System/Library/Fonts/Supplemental"),Path("/usr/share/fonts/truetype/dejavu")]:
        for filename in names[family]:
            if (base/filename).exists():
                return ImageFont.truetype(str(base/filename),size)
    raise FileNotFoundError("Set FIGURE_FONTS to a directory containing Arial or DejaVu fonts")


def label(x,y,text,size,style="regular",fill=ink):
    draw.text((x,y),text,fill=fill,font=font(size,style),anchor="lt")


label(35,29,"SIBOGA EXPEDITION    /    SAPEH STRAIT",18,"bold")
label(32,72,"One letter, 300 metres of depth",45,"serif")
label(35,148,"The species account records one shell at 69 metres.",24)
with Image.open(HERE.parent/"corpus/pages/siboga-p112.png") as page:
    crop = ImageOps.autocontrast(page.crop((314,1768,845,1800))).convert("RGB")
draw.rounded_rectangle((35,194,765,266),radius=6,fill="#ffffff",outline="#c6d1c9")
img.paste(crop.resize((664,40),Image.Resampling.LANCZOS),(50,211))
label(35,284,"Both OCR pipelines read the identifier as 49.",22)
label(35,346,"Depth in the ship’s independent station register",23,"bold")
for y,code,depth,color in [(403,"49",369,"#698a97"),(465,"49A",69,"#147268")]:
    label(36,y,code,26,"bold")
    right=151+round(468*depth/369)
    draw.rounded_rectangle((151,y-1,right,y+25),radius=4,fill=color)
    label(right+12,y+1,f"{depth} m",23,"bold",color)
draw.line((35,531,765,531),fill="#b4c6bf",width=1)
label(35,553,"The depth and locality identify the haul as station 49A.",24,"bold")
label(35,596,"Schepman, p. 112  ·  Tydeman, station register, p. 4",18,fill=muted)
img.save(HERE/"station-49a.png",optimize=True)
