#!/usr/bin/env python3
import argparse, subprocess, sys
from pathlib import Path
from PIL import Image, ImageFilter

# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def build_shadow(icon: Image.Image, blur: int) -> Image.Image:
    alpha = icon.split()[-1]
    shadow = Image.new("RGBA", icon.size, (0, 0, 0, 255))
    shadow.putalpha(alpha)
    return shadow.filter(ImageFilter.GaussianBlur(blur))

def make_icon_layer(src: str, canvas_size: int, blur: int, offset: int, margin: int) -> Image.Image:
    """
    Returns a transparent layer canvas_size×canvas_size with:
      - your icon thumbnail’d to (canvas_size - 2*margin)
      - a drop shadow if blur>0+offset
    """
    icon = Image.open(src).convert("RGBA")
    thumb = max(canvas_size - 2*margin, 1)
    icon.thumbnail((thumb, thumb), Image.LANCZOS)

    layer = Image.new("RGBA", (canvas_size, canvas_size), (0,0,0,0))
    if blur > 0:
        sh = build_shadow(icon, blur)
        x = (canvas_size - sh.width)  // 2 + offset
        y = (canvas_size - sh.height) // 2 + offset
        layer.paste(sh, (x, y), sh)

    x = (canvas_size - icon.width)  // 2
    y = (canvas_size - icon.height) // 2
    layer.paste(icon, (x, y), icon)
    return layer

# --------------------------------------------------------------------
# PNG generation (templates next to script, score inset margin removed)
# --------------------------------------------------------------------
def create_png_set(src: str, ns: str, out: Path, tpl_dir: Path):
    out.mkdir(parents=True, exist_ok=True)

    # 1) tab_<ns>.png  → 16×16 transparent
    tab = make_icon_layer(src, 16, blur=0, offset=0, margin=0)
    tab.save(out / f"tab_{ns}.png")

    # 2) score, sprite, icon
    specs = [
        # variant, default_size, blur, offset, margin, template_filename
        ("score", 64,  0, 0, 0,  "score_template.png"),   # margin set to 0
        ("sprite",256, 3, 2,  3, "sprite_template.png"),
        ("icon",  256, 5, 4,  10, "icon_template.png"), #went from 5 to 10 margin, untested
    ]

    for variant, dsize, blur, offset, margin, tpl in specs:
        if variant == "score":
            # ignore any score_template.png — always blank 64×64
            canvas = Image.new("RGBA", (dsize, dsize), (0,0,0,0))
            size   = dsize
        else:
            tpl_path = tpl_dir / tpl
            if tpl_path.exists():
                canvas = Image.open(tpl_path).convert("RGBA")
                size   = canvas.width
            else:
                canvas = Image.new("RGBA", (dsize, dsize), (0,0,0,0))
                size   = dsize

        layer = make_icon_layer(src, size, blur=blur, offset=offset, margin=margin)
        x = (size - layer.width)  // 2
        y = (size - layer.height) // 2
        canvas.paste(layer, (x, y), layer)
        canvas.save(out / f"{variant}_{ns}.png")

# --------------------------------------------------------------------
# .vmt generation (ignorez only in _noz.vmt)
# --------------------------------------------------------------------
def generate_vmt_files(out: Path, ns: str):
    base_path = f"vgui/ttt/roles/{ns}"
    def write(path: Path, basetex: str, ignorez: bool):
        lines = [
            '"UnlitGeneric"',
            "{",
            f'\t"$basetexture" "{base_path}/{basetex}"',
            "\t$nocull 1",
        ]
        if ignorez:
            lines.append("\t$ignorez 1")
        lines += [
            "\t$nodecal 1",
            "\t$nolod 1",
            "\t$vertexcolor 1",
            "\t$vertexalpha 1",
            "\t$translucent 1",
            "}",
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # sprite.vmt (no ignorez)
    write(out / f"sprite_{ns}.vmt",      f"sprite_{ns}", False)
    # sprite_noz.vmt (with ignorez)
    write(out / f"sprite_{ns}_noz.vmt", f"sprite_{ns}", True)
    # icon.vmt (no ignorez)
    write(out / f"icon_{ns}.vmt",        f"icon_{ns}", False)

# --------------------------------------------------------------------
# VTF conversion
# --------------------------------------------------------------------
VTF_CMD = Path(r"E:\Garry\Software\vtflib132-bin\bin\x64\VTFCmd.exe")

def convert_vtf(out: Path, ns: str, skip: bool):
    if skip:
        print("– Skipping VTF conversion.")
        return
    if not VTF_CMD.exists():
        print(f"⚠️  VTFCmd.exe not found at {VTF_CMD!r}; skipping.")
        return

    for name in (f"sprite_{ns}", f"icon_{ns}"):
        png = out / f"{name}.png"
        try:
            print(f"→ Converting {png.name} …")
            subprocess.run(
                [str(VTF_CMD), "-file", str(png), "-output", str(out)],
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"⚠️  VTFCmd failed on {png.name}: exit {e.returncode}")

# --------------------------------------------------------------------
# CLI & main
# --------------------------------------------------------------------
def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--image",     required=True, help="Base PNG")
    ap.add_argument("--nameraw",   required=True)
    ap.add_argument("--nameshort", required=True, help="lowercase")
    ap.add_argument("--out",       default="RoleAddon")
    ap.add_argument("--no-vtf",    action="store_true")
    args = ap.parse_args(argv)

    if not args.nameshort.islower():
        sys.exit("Error: nameshort must be lowercase")

    script_folder = Path(__file__).resolve().parent
    out_dir       = Path(args.out) / "converted" / args.nameshort

    create_png_set(
        src=args.image,
        ns=args.nameshort,
        out=out_dir,
        tpl_dir=script_folder
    )

    convert_vtf(
        out=out_dir,
        ns=args.nameshort,
        skip=args.no_vtf
    )

    generate_vmt_files(out_dir, args.nameshort)

if __name__ == "__main__":
    main(sys.argv[1:])
