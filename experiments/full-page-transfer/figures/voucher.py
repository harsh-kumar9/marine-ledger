"""Make a specimen evidence plate from the Naturalis CC0 photograph of RMNH.MOL.193497."""

import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("photo", type=Path)
args = parser.parse_args()
bg = Image.new("RGB",(820,834),"#f8f6ee")
draw = ImageDraw.Draw(bg)
for fonts in [Path("/System/Library/Fonts/Supplemental"),Path("/usr/share/fonts/truetype/dejavu")]:
    if (fonts/"Arial.ttf").exists():
        fontnames = ("Arial.ttf","Arial Bold.ttf","Georgia.ttf")
        break
    if (fonts/"DejaVuSans.ttf").exists():
        fontnames = ("DejaVuSans.ttf","DejaVuSans-Bold.ttf","DejaVuSerif.ttf")
        break


def text(x,y,string,size,style=0):
    draw.text((x,y),string,fill="#153f47",font=ImageFont.truetype(str(fonts/fontnames[style]),size),anchor="lt")


text(34,31,"SIBOGA STATION 164    /    HALMAHERA SEA",18,1)
text(32,75,"One shell, two paths to a name",43,2)
with Image.open(args.photo) as source:
    w,h = source.size
    photo = source.crop((int(.18*w),int(.075*h),int(.765*w),int(.835*h)))
    photo.thumbnail((458,351),Image.Resampling.LANCZOS)
    bg.paste(photo,(34,157))
    label = source.crop((int(.197*w),int(.098*h),int(.452*w),int(.359*h)))
    label = ImageOps.autocontrast(label.convert("L")).convert("RGB")
    label.thumbnail((263,169),Image.Resampling.LANCZOS)
    bg.paste(label,(502,164))
text(502,349,"The older label says",21)
text(502,382,"station 164.",26,1)
text(502,440,"Naturalis specimen",17)
text(502,467,"RMNH.MOL.193497",17,1)
draw.line((34,532,786,532),fill="#b5c6c1")
text(34,557,"Museum’s current identification",21)
text(34,594,"Monoplex vespaceus",28,1)
text(34,650,"Registry’s accepted name for the report’s historical gracilis",21)
text(34,685,"Reticutriton pfeifferianus",28,1)
text(34,753,"Which identification fits the specimen? Its determination history",22)
text(34,783,"and a fresh examination could settle the question.",22)
bg.save(HERE/"station-164-voucher.png",optimize=True)
