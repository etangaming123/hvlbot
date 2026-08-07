"""
Quote image generator.

No discord.py dependency on purpose: takes plain strings/bytes in, hands a
PNG back out. Callers (main.py, or a standalone test script) do the
discord-specific work of resolving mentions/avatars before calling in here.
"""
import os
import re
import io
import traceback
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import emoji as emojilib
from fontTools.ttLib import TTFont

CUSTOM_EMOJI_RE = re.compile(r"<(a?):(\w+):(\d+)>")

# Ordered longest-delimiter-first so "***"/"**" aren't shadowed by a "*" match,
# and so each delimiter is matched against its own literal string (not just
# style name) when deciding whether a marker opens or closes a run.
MARKDOWN_DELIMS = [
    ("```", frozenset({"code"})),
    ("***", frozenset({"bold", "italic"})),
    ("~~", frozenset({"strike"})),
    ("**", frozenset({"bold"})),
    ("__", frozenset({"underline"})),
    ("||", frozenset({"spoiler"})),
    ("`", frozenset({"code"})),
    ("*", frozenset({"italic"})),
    ("_", frozenset({"italic"})),
]
CODE_FENCE_LANG_RE = re.compile(r"[A-Za-z0-9_+-]*\n")

FALLBACK_FONT_PATHS = [
    r"C:\Windows\Fonts\seguisym.ttf",  # Segoe UI Symbol: broad symbol/script coverage
    r"C:\Windows\Fonts\msyh.ttc",      # Microsoft YaHei: Chinese
    r"C:\Windows\Fonts\malgun.ttf",    # Malgun Gothic: Korean
    r"C:\Windows\Fonts\meiryo.ttc",    # Meiryo: Japanese
    r"C:\Windows\Fonts\arial.ttf",     # Arial: broad Latin/Cyrillic/Greek fallback
]

_cmap_cache = {}
_font_obj_cache = {}
_emoji_img_cache = {}

def fontHasGlyph(path, ch):
    if ch.isspace():
        return True
    if path not in _cmap_cache:
        try:
            ttf = TTFont(path, lazy=True)
            cmap = ttf.getBestCmap() or {}
            ttf.close()
            _cmap_cache[path] = cmap
        except Exception:
            return False  # don't cache the failure; retry next time in case it was transient
    return ord(ch) in _cmap_cache[path]

def choosePathForChar(ch, primary_path):
    if fontHasGlyph(primary_path, ch):
        return primary_path
    for fp in FALLBACK_FONT_PATHS:
        if os.path.exists(fp) and fontHasGlyph(fp, ch):
            return fp
    return primary_path  # last resort: may render as tofu, better than crashing

def getFontObj(path, size):
    key = (path, size)
    if key not in _font_obj_cache:
        try:
            _font_obj_cache[key] = ImageFont.truetype(path, size)
        except Exception:
            return ImageFont.load_default()  # don't cache the failure; retry next time in case it was transient
    return _font_obj_cache[key]

def buildRuns(word, size, primary_path):
    # split a word into (text, font) runs so mixed-script words each render with a font that has the glyphs
    runs = []
    cur_path, cur_text = None, ""
    for ch in word:
        path = choosePathForChar(ch, primary_path)
        if path == cur_path:
            cur_text += ch
        else:
            if cur_text:
                runs.append((cur_text, getFontObj(cur_path, size)))
            cur_path, cur_text = path, ch
    if cur_text:
        runs.append((cur_text, getFontObj(cur_path, size)))
    return runs

def parseDiscordMarkdown(text):
    """Strip Discord markdown delimiters, returning (plain_text, style_ranges).

    style_ranges is a list of (start, end, frozenset_of_styles) covering
    plain_text contiguously. A delimiter only opens a run if its matching
    close exists later in the string; otherwise it's kept as a literal
    character, same fallback Discord itself uses for malformed markdown.
    """
    n = len(text)
    i = 0
    pos = 0
    plain = []
    ranges = []
    stack = []  # (delim, style)
    cur_buf = []

    def active_style():
        style = frozenset()
        for _, st in stack:
            style |= st
        return style

    def flush_buf():
        nonlocal pos
        if cur_buf:
            piece = "".join(cur_buf)
            plain.append(piece)
            ranges.append((pos, pos + len(piece), active_style()))
            pos += len(piece)
            cur_buf.clear()

    while i < n:
        matched = None
        for delim, style in MARKDOWN_DELIMS:
            if text.startswith(delim, i):
                matched = (delim, style)
                break
        if matched is None:
            cur_buf.append(text[i])
            i += 1
            continue
        delim, style = matched
        if stack and stack[-1][0] == delim:
            flush_buf()
            stack.pop()
            i += len(delim)
            continue
        if text.find(delim, i + len(delim)) == -1:
            cur_buf.append(text[i])
            i += 1
            continue
        flush_buf()
        stack.append((delim, style))
        i += len(delim)
        if delim == "```":
            m = CODE_FENCE_LANG_RE.match(text, i)
            if m:
                i = m.end()
    flush_buf()
    return "".join(plain), ranges

def styleFor(style_ranges, span_start, span_end):
    # a word can straddle a style boundary when markdown touches text with no
    # surrounding space (e.g. "un**believable**"); use whichever style covers
    # most of the span rather than just the first character's style
    best_style, best_overlap = frozenset(), 0
    for start, end, style in style_ranges:
        overlap = min(end, span_end) - max(start, span_start)
        if overlap > best_overlap:
            best_overlap, best_style = overlap, style
    return best_style

def findEmojiSpans(text):
    spans = [(m.start(), m.end(), "custom", {"animated": bool(m.group(1)), "name": m.group(2), "id": m.group(3)}) for m in CUSTOM_EMOJI_RE.finditer(text)]
    spans += [(e["match_start"], e["match_end"], "unicode", {"char": e["emoji"]}) for e in emojilib.emoji_list(text)]
    spans.sort(key=lambda s: s[0])
    filtered, last_end = [], 0
    for s in spans:
        if s[0] >= last_end:
            filtered.append(s)
            last_end = s[1]
    return filtered

def safeTruncate(text, max_chars):
    if len(text) <= max_chars:
        return text, 0
    cut = max_chars
    for start, end, _, _ in findEmojiSpans(text):
        if start < cut < end:
            cut = start
    return text[:cut], len(text) - cut

def tokenizeContent(text):
    plain_text, style_ranges = parseDiscordMarkdown(text)
    spans = findEmojiSpans(plain_text)
    tokens, pos = [], 0
    for start, end, kind, data in spans:
        if start > pos:
            tokens.append(("text", plain_text[pos:start], pos, start))
        tokens.append((kind, data, start, end))
        pos = end
    if pos < len(plain_text):
        tokens.append(("text", plain_text[pos:], pos, len(plain_text)))
    atoms = []
    for kind, data, start_pos, end_pos in tokens:
        if kind == "text":
            for m in re.finditer(r"\S+", data):
                atoms.append(("word", m.group(0), styleFor(style_ranges, start_pos + m.start(), start_pos + m.end())))
        else:
            atoms.append((kind, data, styleFor(style_ranges, start_pos, end_pos)))
    return atoms

BOLD_STROKE = 1
ITALIC_SHEAR = 0.22
CODE_BG = (40, 40, 40)
CODE_FG = (255, 200, 120)

def runWidth(draw, text, font, style):
    stroke_w = BOLD_STROKE if "bold" in style else 0
    w = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_w)[2]
    if "italic" in style:
        w += int(font.size * ITALIC_SHEAR)
    return w

def drawStyledRun(img, draw, x, y, text, font, color, style):
    """Draw one (text, font) run with Discord-style emphasis, return width consumed.

    Bold is faked with a text outline stroke (no bold font file guaranteed to
    exist), italic by shearing the glyphs on a scratch RGBA layer and
    pasting the result, since PIL has no native oblique transform.
    """
    stroke_w = BOLD_STROKE if "bold" in style else 0
    fill = CODE_FG if "code" in style else color
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_w)
    plain_w = bbox[2]

    if "italic" in style:
        left, top, right, bottom = bbox
        left, top = min(left, 0), min(top, 0)
        tmp_w, tmp_h = right - left, bottom - top
        shift = int(tmp_h * ITALIC_SHEAR)
        tmp = Image.new("RGBA", (tmp_w, tmp_h), (0, 0, 0, 0))
        ImageDraw.Draw(tmp).text((-left, -top), text, font=font, fill=fill, stroke_width=stroke_w, stroke_fill=fill)
        sheared = tmp.transform((tmp_w + shift, tmp_h), Image.AFFINE, (1, ITALIC_SHEAR, 0, 0, 1, 0), resample=Image.BICUBIC)
        if "code" in style:
            draw.rectangle([x - 4, y - 2, x + plain_w + shift + 4, y + font.size + 4], fill=CODE_BG)
        img.paste(sheared, (x + left, y + top), sheared)
        consumed_w = plain_w + shift
    else:
        if "code" in style:
            draw.rectangle([x - 4, y - 2, x + plain_w + 4, y + font.size + 4], fill=CODE_BG)
        draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke_w, stroke_fill=fill)
        consumed_w = plain_w

    line_w = max(1, font.size // 16)
    if "underline" in style:
        ly = y + font.size + 1
        draw.line([(x, ly), (x + consumed_w, ly)], fill=color, width=line_w)
    if "strike" in style:
        ly = y + int(font.size * 0.55)
        draw.line([(x, ly), (x + consumed_w, ly)], fill=color, width=line_w)
    return consumed_w

async def fetchEmojiImage(session, kind, data, size):
    cache_key = (kind, data.get("id") or data.get("char"))
    if cache_key not in _emoji_img_cache:
        raw_img = None
        try:
            if kind == "custom":
                ext = "gif" if data["animated"] else "png"
                async with session.get(f"https://cdn.discordapp.com/emojis/{data['id']}.{ext}") as resp:
                    if resp.status == 200:
                        raw_img = Image.open(io.BytesIO(await resp.read()))
                        raw_img.seek(0)  # first frame if animated
                        raw_img = raw_img.convert("RGBA")
            else:
                codepoints_variants = {
                    "-".join(f"{ord(c):x}" for c in data["char"] if ord(c) != 0xFE0F),
                    "-".join(f"{ord(c):x}" for c in data["char"]),
                }
                for cps in codepoints_variants:
                    async with session.get(f"https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/72x72/{cps}.png") as resp:
                        if resp.status == 200:
                            raw_img = Image.open(io.BytesIO(await resp.read())).convert("RGBA")
                            break
        except Exception:
            raw_img = None
        _emoji_img_cache[cache_key] = raw_img
    raw_img = _emoji_img_cache[cache_key]
    return raw_img.resize((size, size), Image.LANCZOS) if raw_img else None

async def renderQuoteImage(
    content_text,
    author_display_name,
    author_username,
    avatar_bytes,
    font_path,
    role_color=(255, 255, 255),
    max_chars=200,
    watermark_text="rui kamishiro // coded by etangaming123 // join at hvl.etangaming.xyz",
    emoji_session=None,
):
    """Render a quote card and return raw PNG bytes.

    All inputs are plain Python types (strings/bytes), no discord.py objects,
    so this can be called from a bare asyncio script for testing.
    """
    W, H = 1200, 630

    avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")

    # Black background
    img = Image.new('RGB', (W, H), (0, 0, 0))

    # Radial spotlight gradient with user's role color
    y_coords, x_coords = np.mgrid[0:H, 0:W]
    cx, cy = W // 4, H // 2
    max_r = H * 0.78
    dist = np.sqrt((x_coords - cx) ** 2 + (y_coords - cy) ** 2)
    brightness = np.clip(1.0 - dist / max_r, 0, 1) ** 0.55
    brightness = (brightness * 255).astype(np.uint8)

    brightness_f = brightness.astype(np.float32)
    r = (brightness_f * role_color[0] / 255).astype(np.uint8)
    g = (brightness_f * role_color[1] / 255).astype(np.uint8)
    b = (brightness_f * role_color[2] / 255).astype(np.uint8)
    gradient = Image.fromarray(np.stack([r, g, b], axis=2), 'RGB')
    img.paste(gradient, (0, 0), Image.fromarray(brightness))

    # Circular avatar
    av_size = 300
    avatar_img = avatar_img.resize((av_size, av_size), Image.LANCZOS)
    mask = Image.new('L', (av_size, av_size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, av_size - 1, av_size - 1], fill=255)
    ax, ay = cx - av_size // 2, cy - av_size // 2
    img.paste(avatar_img.convert('RGB'), (ax, ay), mask)

    draw = ImageDraw.Draw(img)

    # Fonts
    try:
        font_name     = ImageFont.truetype(font_path, 38)
        font_username = ImageFont.truetype(font_path, 28)
        font_wm       = ImageFont.truetype(font_path, 20)
    except Exception:
        font_name = font_username = font_wm = ImageFont.load_default()

    # Text area: right half
    tx, ty_pad = W // 2 + 30, 40
    text_w = W - tx - ty_pad

    quote_text, trimmed_chars = safeTruncate(content_text, max_chars)
    if trimmed_chars:
        quote_text += f"... [{trimmed_chars} more characters]"

    atoms = tokenizeContent(quote_text)

    # Prefetch emoji images (unicode + custom Discord emoji) once at a large size, resized per font-size trial
    emoji_images = {}
    async def prefetch(session):
        for kind, data, style in atoms:
            if kind in ("custom", "unicode"):
                key = (kind, data.get("id") or data.get("char"))
                if key not in emoji_images:
                    emoji_images[key] = await fetchEmojiImage(session, kind, data, 128)

    if emoji_session is not None:
        await prefetch(emoji_session)
    else:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            await prefetch(session)

    def elementWidth(el):
        if el[0] == "emoji":
            return el[2]
        runs, style = el[1], el[2]
        return sum(runWidth(draw, t, f, style) for t, f in runs)

    def wrapAtoms(font_size):
        space_w = draw.textbbox((0, 0), " ", font=getFontObj(font_path, font_size))[2]
        lines, cur, cur_w = [], [], 0
        for kind, data, style in atoms:
            if kind == "word":
                el = ("text", buildRuns(data, font_size, font_path), style)
            else:
                img128 = emoji_images.get((kind, data.get("id") or data.get("char")))
                if img128 is None:
                    el = ("text", buildRuns(data.get("char", ""), font_size, font_path), style)
                else:
                    el = ("emoji", img128.resize((font_size, font_size), Image.LANCZOS), font_size)
            w = elementWidth(el)
            add_w = w if not cur else space_w + w
            if cur and cur_w + add_w > text_w:
                lines.append(cur)
                cur, cur_w = [el], w
            else:
                cur.append(el)
                cur_w += add_w
        if cur:
            lines.append(cur)
        return lines, space_w

    # Dynamically shrink font until the wrapped content fits vertically
    max_text_h = H - 80 - (font_name.size + 8) - font_username.size - 20
    font_size = 62
    while font_size >= 16:
        quote_lines, space_w = wrapAtoms(font_size)
        lh = int(font_size * 1.25)
        if len(quote_lines) * lh <= max_text_h:
            break
        font_size -= 2

    lh = int(font_size * 1.25)
    total_q_h = len(quote_lines) * lh
    name_h = font_name.size + 8
    uname_h = font_username.size
    total_h = total_q_h + name_h + uname_h + 20
    start_y = (H - total_h) // 2

    # Quote lines (centered in text area)
    for i, line in enumerate(quote_lines):
        line_w = sum(elementWidth(el) for el in line) + space_w * (len(line) - 1)
        x = tx + (text_w - line_w) // 2
        yy = start_y + i * lh
        for el in line:
            if el[0] == "emoji":
                emoji_img = el[1]
                img.paste(emoji_img, (x, yy), emoji_img)
                x += el[2]
            else:
                runs, style = el[1], el[2]
                for t, f in runs:
                    x += drawStyledRun(img, draw, x, yy, t, f, (255, 255, 255), style)
            x += space_w

    y = start_y + total_q_h + 10

    def drawCenteredRuns(text, size, y_top, color):
        runs = buildRuns(text, size, font_path)
        w = sum(draw.textbbox((0, 0), t, font=f)[2] for t, f in runs)
        x = tx + (text_w - w) // 2
        for t, f in runs:
            draw.text((x, y_top), t, fill=color, font=f)
            x += draw.textbbox((0, 0), t, font=f)[2]

    # "- DisplayName"
    drawCenteredRuns(f"- {author_display_name}", font_name.size, y, (255, 255, 255))
    y += name_h

    # "@username"
    drawCenteredRuns(f"@{author_username}", font_username.size, y, (160, 160, 160))

    # Watermark bottom-right
    draw.text((W - 12, H - 12), watermark_text, fill=(90, 90, 90), font=font_wm, anchor="rb")

    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    buffered.seek(0)
    return buffered.read()
