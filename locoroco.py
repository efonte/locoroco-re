#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import io
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from struct import unpack
from typing import List, Optional

import typer
from PIL import Image
from rich import print
from rich.logging import RichHandler
from rich.progress import TaskID  # SpinnerColumn,
from rich.progress import BarColumn, Progress, TimeRemainingColumn

app = typer.Typer()


# https://github.com/Nezogoku/timp_convert
# https://github.com/owodzeg/libTIMP
def tip_to_png(input: Path, output: Optional[Path]):
    infile = open(
        input,
        mode="rb",
    )
    magic = unpack("4s", infile.read(4))[0].decode("ansi")  # .rstrip("\x00")
    # print(f"{magic=}")
    if magic != "TIMP":
        raise Exception(f"Expected TIMP header. Found {magic}")

    unk1 = infile.read(14)
    # print(f"{unk1=}")
    if unk1 != b"\x01\x00\x01\x00\x10\x00\x00\x00\x00\x00\x00\x00\x18\x00":
        raise Exception(f"Different unk1 value. Found {unk1}")

    width = unpack("H", infile.read(2))[0]
    print(f"{width=}")

    height = unpack("H", infile.read(2))[0]
    print(f"{height=}")

    unk2 = infile.read(3)
    # print(f"{unk2=}")
    if unk2 != b"\x01\x00\x03":
        raise Exception(f"Different unk2 value. Found {unk2}")

    palette_type = unpack("B", infile.read(1))[0]
    print(f"{palette_type=}")
    # if palette_type != 5:
    #     raise Exception(f"Different palette_type value. Found {palette_type}")

    unk3 = infile.read(6)
    # print(f"{unk3=}")
    if unk3 != b"\x01\x01\x00\x00\x00\x00":
        raise Exception(f"Different unk3 value. Found {unk3}")

    offset_palette = unpack("I", infile.read(4))[0]
    print(f"{offset_palette=:08X}")

    offset_pixels = unpack("I", infile.read(4))[0]
    print(f"{offset_pixels=:08X}")

    padding1 = infile.read(8)
    # print(f"{padding1=}")
    if padding1 != b"\x00" * 8:
        raise Exception(f"Expected padding. Found {padding1}")

    palette_colors = (offset_pixels - offset_palette) // 4 if offset_palette != 0 else 0
    print(f"{palette_colors=}")

    noPal = offset_pixels == 0x10

    # Apply swizzling
    if palette_colors == 0:
        noPal = True
        chunk_w = 4
        chunk_h = 8
    elif palette_colors == 16:
        chunk_w = 32
        chunk_h = 8
    elif palette_colors == 32:
        chunk_w = 32
        chunk_h = 8
    elif palette_colors == 64:
        chunk_w = 16
        chunk_h = 8
    elif palette_colors == 48:
        chunk_w = 32
        chunk_h = 8
    elif palette_colors == 96:
        chunk_w = 32
        chunk_h = 8
    elif palette_colors == 112:
        chunk_w = 32
        chunk_h = 8
    elif palette_colors == 236:
        chunk_w = 16
        chunk_h = 8
    elif palette_colors == 256:
        chunk_w = 16
        chunk_h = 8

    print(f"{chunk_w=}")
    print(f"{chunk_h=}")

    if infile.tell() != offset_palette:
        raise Exception(f"Expected {offset_palette} offset. Found {offset_palette}")

    # read palette
    num_empty_colors = 0
    palette = []
    for _ in range(palette_colors):
        r, g, b, a = unpack("4B", infile.read(4))
        palette.append((r, g, b, a))
        if (
            (r == 0x00 and g == 0x00 and b == 0x00)
            or (r == 0xFF and g == 0xFF and b == 0xFF)
        ) and (a == 0x00 or a == 0xFF):
            num_empty_colors += 1

    print(f"{num_empty_colors=}")
    print(f"{len(palette)=}")

    # Determine true pixel data size
    used_bytes = 0

    # if width % chunk_w == 0 and height % chunk_h == 0:
    #     # Amount of pixels
    #     px_length = width * height
    #     # px_length = chunk_h * chunk_w
    #     # print(width * height)
    #     # print(chunk_h * chunk_w)
    #     used_bytes = px_length
    # else:
    #     amntX = math.ceil(width / chunk_w)
    #     amntY = math.ceil(height / chunk_h)
    #     used_bytes = (chunk_w * amntX) * (chunk_h * amntY)
    #     print(f"{amntX=}")
    #     print(f"{amntY=}")

    infile.seek(0, io.SEEK_END)
    used_bytes = infile.tell() - offset_pixels

    print(f"{used_bytes=}")

    pixels = []
    # If palette exists, read pixels according to palette
    if not noPal:
        for i in range(used_bytes):
            infile.seek(offset_pixels + i)
            # try:
            pixel = unpack("B", infile.read(1))[0]
            # except Exception:
            #     # print(f"{offset_pixels+i:X}")
            #     # TODO: Fix baria_icon.tip
            #     continue

            if palette_colors == 64 or palette_colors >= 200:  # 8 bits per pixel
                if pixel >= len(palette):
                    pixel = len(palette) - 1
                pixels.append(pixel)
            elif palette_colors < 200:  # 4 bits per pixel
                pixels.append(pixel & 0xF)
                pixels.append((pixel >> 4) & 0xF)

            # size_of_data = infile.tell()

    else:  # If palette doesn't exist, read colours from pixels
        # print("noPal=True")
        # exit()
        max_pal = 0x00
        for i in range(used_bytes):
            r, g, b, a = unpack("4B", infile.read(4))

            palette.append((r, g, b, a))
            pixels.append(len(palette) - 1)

            max_pal = max(max_pal, r)
            max_pal = max(max_pal, g)
            max_pal = max(max_pal, b)
            max_pal = max(max_pal, a)

            # size_of_data = infile.tell()

        if max_pal >= 48:
            palette_colors = 256
        elif max_pal >= 16:
            palette_colors = 48
        else:
            palette_colors = 16

    print(f"{len(pixels)=}")
    # print(f"0x{size_of_data:X=}")

    x, y = 0, 0
    p = 0
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    while p < len(pixels):
        for ch in range(chunk_h):
            for cw in range(chunk_w):
                if (x + cw) < width and (y + ch) < height:
                    img.putpixel((x + cw, y + ch), palette[pixels[p]])
                # Pixels are incremented nonetheless so swizzling can work on textures with sizes that are not a power of 2
                p += 1
        x += chunk_w
        if x >= width:
            x = 0
            y += chunk_h

        # if y >= height:
        #     break

    if not output or output.suffix != ".png":
        output = input.parent.joinpath(f"{input.stem}.png")
    # if output.is_file():
    #     raise Exception(f"File {output} already exists")

    img.save(output)


@app.command()
def tip_convert(
    input: Path = typer.Argument(..., help="TIP image or folder path"),
    output: Path = typer.Option(
        None, "--output", "-o", help="PNG image or folder path"
    ),
    # recursive: bool = typer.Option(
    #     False, "--recursive", "-r", help="Recursive directories"
    # ),
    skip_existing: bool = typer.Option(
        False,
        "--skip-existing",
        "-se",
        help="Skip existing png files",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose mode",
    ),
):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(markup=True)],
        # handlers=[RichHandler(markup=True, rich_tracebacks=True)],
    )
    log = logging.getLogger("rich")

    if skip_existing and output.is_file():
        log.error(f'File "{output}" already exists')
        raise typer.Abort()

    if input.is_dir():
        tip_images: List[Path] = list(input.glob("*.tip"))
        # tip_images: List[Path] = list(input.glob("*.cip"))
        with Progress(
            # SpinnerColumn(),
            "[progress.description]{task.description}",
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("Converting", total=len(tip_images))
            for idx, tip_path in enumerate(tip_images, 1):
                tip_path_rel = tip_path.relative_to(input)
                if output and output.is_dir():
                    png_path = output.joinpath(
                        tip_path_rel.parent.joinpath(f"{tip_path.stem}.png")
                    )
                else:
                    png_path = tip_path.parent.joinpath(f"{tip_path.stem}.png")
                log.info(
                    f'Processing {str(idx).zfill(len(str(len(tip_images))))}: "{tip_path_rel}"'
                )
                if skip_existing and png_path.is_file():
                    log.warning("Already exists, skipping")
                    progress.advance(task)
                    continue
                tip_to_png(tip_path, png_path)
                print("---")
                # exit()
                progress.advance(task)

    else:
        if not output or output.suffix != ".png":
            output = input.parent.joinpath(f"{input.stem}.png")

        tip_to_png(input, output)


if __name__ == "__main__":
    app()
