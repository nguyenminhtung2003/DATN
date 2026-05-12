from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape


OUT = Path(__file__).with_name("DrowsiGuard_Bao_Cao_Do_An_Tot_Nghiep.pptx")
EMU = 914400
SLIDE_W = 12192000
SLIDE_H = 6858000


def emu(value_in_inches: float) -> int:
    return int(round(value_in_inches * EMU))


def rgb(value: str) -> str:
    return value.replace("#", "").upper()


def xtext(value: str) -> str:
    return escape(value, {"\n": "&#10;"})


PALETTE = {
    "navy": "0B2E4A",
    "teal": "0F766E",
    "mint": "DDF7F0",
    "cyan": "D8F0F5",
    "blue": "EAF4FB",
    "white": "FFFFFF",
    "ink": "123047",
    "muted": "5C7486",
    "line": "A9CCD4",
    "green": "17A673",
    "yellow": "F2B705",
    "red": "D64545",
    "dark": "061B2A",
    "soft": "F7FBFC",
}


@dataclass
class Shape:
    kind: str
    x: float
    y: float
    w: float
    h: float
    text: str = ""
    font_size: int = 18
    color: str = PALETTE["ink"]
    fill: Optional[str] = None
    line: Optional[str] = None
    bold: bool = False
    align: str = "l"
    radius: str = "roundRect"
    margin: float = 0.08
    valign: str = "mid"
    name: str = "Shape"
    level: int = 0
    arrow: bool = False
    line_width: float = 1.5


@dataclass
class Slide:
    title: str
    kicker: str = ""
    shapes: List[Shape] = field(default_factory=list)
    dark: bool = False

    def textbox(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        text: str,
        font_size: int = 18,
        color: str = PALETTE["ink"],
        bold: bool = False,
        align: str = "l",
        margin: float = 0.05,
        valign: str = "mid",
    ) -> None:
        self.shapes.append(
            Shape(
                "textbox",
                x,
                y,
                w,
                h,
                text=text,
                font_size=font_size,
                color=color,
                bold=bold,
                align=align,
                margin=margin,
                valign=valign,
            )
        )

    def box(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        text: str,
        fill: str = PALETTE["white"],
        line: str = PALETTE["line"],
        font_size: int = 17,
        color: str = PALETTE["ink"],
        bold: bool = False,
        align: str = "ctr",
        radius: str = "roundRect",
    ) -> None:
        self.shapes.append(
            Shape(
                "box",
                x,
                y,
                w,
                h,
                text=text,
                font_size=font_size,
                color=color,
                fill=fill,
                line=line,
                bold=bold,
                align=align,
                radius=radius,
            )
        )

    def line_shape(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        color: str = PALETTE["teal"],
        arrow: bool = True,
        line_width: float = 1.7,
    ) -> None:
        self.shapes.append(
            Shape(
                "line",
                x,
                y,
                w,
                h,
                fill=None,
                line=color,
                arrow=arrow,
                line_width=line_width,
            )
        )

    def bullets(
        self,
        x: float,
        y: float,
        w: float,
        items: Sequence[str],
        font_size: int = 17,
        color: str = PALETTE["ink"],
        gap: float = 0.36,
    ) -> None:
        for idx, item in enumerate(items):
            self.textbox(
                x,
                y + idx * gap,
                w,
                0.28,
                f"• {item}",
                font_size=font_size,
                color=color,
                valign="top",
            )


def r_pr(font_size: int, color: str, bold: bool) -> str:
    b = ' b="1"' if bold else ""
    return (
        f'<a:rPr lang="vi-VN" sz="{font_size * 100}"{b}>'
        f'<a:solidFill><a:srgbClr val="{rgb(color)}"/></a:solidFill>'
        "</a:rPr>"
    )


def paragraph(text: str, font_size: int, color: str, bold: bool, align: str) -> str:
    runs = []
    parts = text.split("\n")
    for idx, part in enumerate(parts):
        if idx:
            runs.append("<a:br/>")
        runs.append(f"<a:r>{r_pr(font_size, color, bold)}<a:t>{xtext(part)}</a:t></a:r>")
    return f'<a:p><a:pPr algn="{align}"/>' + "".join(runs) + "</a:p>"


def sp_xml(shape: Shape, shape_id: int) -> str:
    x, y, w, h = emu(shape.x), emu(shape.y), emu(shape.w), emu(shape.h)
    margin = emu(shape.margin)
    if shape.kind == "line":
        head = '<a:headEnd type="triangle"/>' if shape.arrow else ""
        return f"""
<p:cxnSp>
  <p:nvCxnSpPr><p:cNvPr id="{shape_id}" name="Connector {shape_id}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>
    <a:prstGeom prst="line"><a:avLst/></a:prstGeom>
    <a:ln w="{int(shape.line_width * 12700)}">
      <a:solidFill><a:srgbClr val="{rgb(shape.line or PALETTE['teal'])}"/></a:solidFill>
      {head}
    </a:ln>
  </p:spPr>
</p:cxnSp>"""

    fill = (
        f'<a:solidFill><a:srgbClr val="{rgb(shape.fill)}"/></a:solidFill>'
        if shape.fill
        else "<a:noFill/>"
    )
    line = (
        f'<a:ln w="9525"><a:solidFill><a:srgbClr val="{rgb(shape.line)}"/></a:solidFill></a:ln>'
        if shape.line
        else '<a:ln><a:noFill/></a:ln>'
    )
    text = paragraph(shape.text, shape.font_size, shape.color, shape.bold, shape.align)
    body = (
        f'<p:txBody><a:bodyPr wrap="square" lIns="{margin}" tIns="{margin}" '
        f'rIns="{margin}" bIns="{margin}" anchor="{shape.valign}"/>'
        f"<a:lstStyle/>{text}</p:txBody>"
    )
    return f"""
<p:sp>
  <p:nvSpPr><p:cNvPr id="{shape_id}" name="{shape.name} {shape_id}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>
    <a:prstGeom prst="{shape.radius}"><a:avLst/></a:prstGeom>
    {fill}
    {line}
  </p:spPr>
  {body}
</p:sp>"""


def slide_xml(slide: Slide, slide_no: int) -> str:
    bg = PALETTE["dark"] if slide.dark else PALETTE["soft"]
    title_color = PALETTE["white"] if slide.dark else PALETTE["navy"]
    kicker_color = "85E4D2" if slide.dark else PALETTE["teal"]
    base_shapes = [
        Shape("box", 0, 0, 13.333, 7.5, fill=bg, line=bg, radius="rect"),
        Shape("box", 0, 0, 13.333, 0.22, fill=PALETTE["teal"], line=PALETTE["teal"], radius="rect"),
        Shape(
            "textbox",
            0.58,
            0.38,
            11.3,
            0.2,
            text=slide.kicker.upper() if slide.kicker else "DROWSIGUARD",
            font_size=8,
            color=kicker_color,
            bold=True,
            valign="top",
        ),
        Shape(
            "textbox",
            0.55,
            0.62,
            11.7,
            0.62,
            text=slide.title,
            font_size=25,
            color=title_color,
            bold=True,
            valign="top",
        ),
        Shape(
            "textbox",
            11.78,
            6.92,
            0.92,
            0.22,
            text=f"{slide_no:02d}",
            font_size=10,
            color=PALETTE["muted"] if not slide.dark else "B8D7DF",
            bold=True,
            align="r",
        ),
    ]
    all_shapes = base_shapes + slide.shapes
    body = "\n".join(sp_xml(shape, idx + 2) for idx, shape in enumerate(all_shapes))
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{SLIDE_W}" cy="{SLIDE_H}"/><a:chOff x="0" y="0"/><a:chExt cx="{SLIDE_W}" cy="{SLIDE_H}"/></a:xfrm></p:grpSpPr>
      {body}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def content_types(slide_count: int) -> str:
    overrides = "\n".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, slide_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>
  <Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>
  <Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>
  {overrides}
</Types>"""


def root_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def presentation_xml(slide_count: int) -> str:
    sld_ids = "\n".join(
        f'<p:sldId id="{255 + i}" r:id="rId{i + 4}"/>' for i in range(1, slide_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>{sld_ids}</p:sldIdLst>
  <p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
  <p:defaultTextStyle>
    <a:defPPr><a:defRPr lang="vi-VN"/></a:defPPr>
  </p:defaultTextStyle>
</p:presentation>"""


def presentation_rels(slide_count: int) -> str:
    rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>',
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps" Target="presProps.xml"/>',
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps" Target="viewProps.xml"/>',
        '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles" Target="tableStyles.xml"/>',
    ]
    rels.extend(
        f'<Relationship Id="rId{i + 4}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, slide_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels)
        + "</Relationships>"
    )


def common_slide_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>"""


def slide_master() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{SLIDE_W}" cy="{SLIDE_H}"/><a:chOff x="0" y="0"/><a:chExt cx="{SLIDE_W}" cy="{SLIDE_H}"/></a:xfrm></p:grpSpPr>
  </p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>
</p:sldMaster>"""


def slide_layout() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{SLIDE_W}" cy="{SLIDE_H}"/><a:chOff x="0" y="0"/><a:chExt cx="{SLIDE_W}" cy="{SLIDE_H}"/></a:xfrm></p:grpSpPr>
  </p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""


def theme() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="DrowsiGuard">
  <a:themeElements>
    <a:clrScheme name="DrowsiGuard">
      <a:dk1><a:srgbClr val="061B2A"/></a:dk1>
      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="0B2E4A"/></a:dk2>
      <a:lt2><a:srgbClr val="F7FBFC"/></a:lt2>
      <a:accent1><a:srgbClr val="0F766E"/></a:accent1>
      <a:accent2><a:srgbClr val="17A673"/></a:accent2>
      <a:accent3><a:srgbClr val="F2B705"/></a:accent3>
      <a:accent4><a:srgbClr val="D64545"/></a:accent4>
      <a:accent5><a:srgbClr val="5C7486"/></a:accent5>
      <a:accent6><a:srgbClr val="D8F0F5"/></a:accent6>
      <a:hlink><a:srgbClr val="0F766E"/></a:hlink>
      <a:folHlink><a:srgbClr val="5C7486"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Aptos"><a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme>
    <a:fmtScheme name="DrowsiGuard"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle/></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>
  </a:themeElements>
  <a:objectDefaults/>
  <a:extraClrSchemeLst/>
</a:theme>"""


def app_xml(slide_count: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
            xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
  <PresentationFormat>On-screen Show (16:9)</PresentationFormat>
  <Slides>{slide_count}</Slides>
  <Company>DrowsiGuard</Company>
</Properties>"""


def core_xml() -> str:
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:dcmitype="http://purl.org/dc/dcmitype/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>DrowsiGuard - Bao cao do an tot nghiep</dc:title>
  <dc:subject>AI drowsiness warning system</dc:subject>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{stamp}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{stamp}</dcterms:modified>
</cp:coreProperties>"""


def extra_props() -> Tuple[str, str, str, str, str, str]:
    pres_props = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentationPr xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>"""
    view_props = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:viewPr xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>"""
    table_styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:tblStyleLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" def="{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"/>"""
    master_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>"""
    layout_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>"""
    return pres_props, view_props, table_styles, master_rels, layout_rels, theme()


def build_slides() -> List[Slide]:
    slides: List[Slide] = []

    s = Slide("DrowsiGuard", "Báo cáo đồ án tốt nghiệp", dark=True)
    s.textbox(0.7, 1.55, 8.6, 0.72, "Hệ thống cảnh báo buồn ngủ tài xế", 28, PALETTE["white"], True, valign="top")
    s.textbox(0.72, 2.36, 8.8, 0.36, "Jetson Nano • Camera • RFID • GPS • Monitoring Hub thời gian thực", 15, "D8F0F5")
    s.box(0.75, 3.25, 2.1, 0.62, "Edge Runtime\ntrên xe", "0F766E", "50D6C2", 15, PALETTE["white"], True)
    s.box(3.35, 3.25, 2.1, 0.62, "WebSocket\nrealtime", "123047", "50D6C2", 15, PALETTE["white"], True)
    s.box(5.95, 3.25, 2.1, 0.62, "Monitoring Hub\ntrung tâm", "0F766E", "50D6C2", 15, PALETTE["white"], True)
    s.line_shape(2.9, 3.56, 0.36, 0, "85E4D2")
    s.line_shape(5.5, 3.56, 0.36, 0, "85E4D2")
    s.textbox(0.75, 5.62, 5.0, 0.35, "Sinh viên: Bùi Minh Tùng", 16, PALETTE["white"], True)
    s.textbox(0.75, 6.0, 7.0, 0.3, "GVHD / Khoa / Lớp: chỉnh lại theo thông tin chính thức", 12, "B8D7DF")
    slides.append(s)

    s = Slide("Nội dung báo cáo", "Agenda")
    agenda = [
        ("1", "Bài toán, mục tiêu và phạm vi"),
        ("2", "Kiến trúc hệ thống DrowsiGuard"),
        ("3", "Luồng xử lý: RFID, Face ID, AI buồn ngủ"),
        ("4", "WebQuanLi / Monitoring Hub và dữ liệu realtime"),
        ("5", "Kiểm thử, hạn chế, hướng phát triển và demo"),
    ]
    for i, (num, text) in enumerate(agenda):
        y = 1.55 + i * 0.82
        s.box(0.85, y, 0.52, 0.52, num, PALETTE["teal"], PALETTE["teal"], 16, PALETTE["white"], True)
        s.textbox(1.58, y + 0.09, 9.8, 0.32, text, 19, PALETTE["ink"], i == 0)
    slides.append(s)

    s = Slide("Bài toán và mục tiêu", "Why")
    s.box(0.7, 1.5, 3.75, 3.75, "Vấn đề\n\nTài xế có thể mệt mỏi, mất tập trung hoặc buồn ngủ trong quá trình vận hành xe.", PALETTE["blue"], PALETTE["line"], 18, PALETTE["ink"], True)
    s.box(4.8, 1.5, 3.75, 3.75, "Mục tiêu\n\nPhát hiện dấu hiệu buồn ngủ bằng camera và cảnh báo kịp thời tại thiết bị.", PALETTE["mint"], PALETTE["line"], 18, PALETTE["ink"], True)
    s.box(8.9, 1.5, 3.75, 3.75, "Kết quả mong muốn\n\nGiám sát phiên lái, cảnh báo realtime và lưu vết dữ liệu cho quản lý.", "FDF7E7", "E5C669", 18, PALETTE["ink"], True)
    slides.append(s)

    s = Slide("Tên gọi khi trình bày", "Project naming")
    s.box(0.85, 1.52, 5.35, 1.0, "Version3\n→ DrowsiGuard Edge Runtime", PALETTE["mint"], PALETTE["line"], 18, PALETTE["navy"], True)
    s.box(7.05, 1.52, 5.35, 1.0, "WebQuanLi\n→ DrowsiGuard Monitoring Hub", PALETTE["blue"], PALETTE["line"], 18, PALETTE["navy"], True)
    s.bullets(1.0, 3.0, 5.5, ["Version3 là phần mềm chạy trên Jetson Nano trong xe.", "WebQuanLi là trung tâm giám sát, API, WebSocket và dashboard.", "Khi bảo vệ, nên dùng tên chức năng thay vì tên folder."], 16)
    s.box(7.0, 3.05, 4.9, 1.35, "Phiên bản tiếng Việt\n\nPhần mềm thiết bị trên xe\nTrung tâm giám sát DrowsiGuard", "FFFFFF", PALETTE["line"], 15, PALETTE["ink"])
    s.box(7.0, 4.75, 4.9, 1.1, "Phiên bản tiếng Anh\n\nEdge Runtime\nMonitoring Hub", "FFFFFF", PALETTE["line"], 15, PALETTE["ink"])
    slides.append(s)

    s = Slide("Kiến trúc tổng thể", "System overview")
    s.box(0.75, 1.65, 2.2, 0.75, "Camera\nRFID\nGPS / Loa", PALETTE["white"], PALETTE["line"], 15, PALETTE["ink"], True)
    s.box(3.45, 1.48, 2.55, 1.1, "Jetson Nano\nDrowsiGuard Edge Runtime", PALETTE["mint"], PALETTE["teal"], 16, PALETTE["navy"], True)
    s.box(6.65, 1.65, 1.65, 0.75, "Tailscale\nLAN/Wi-Fi", "FDF7E7", "E5C669", 15, PALETTE["ink"], True)
    s.box(8.95, 1.48, 2.8, 1.1, "DrowsiGuard\nMonitoring Hub", PALETTE["blue"], PALETTE["teal"], 16, PALETTE["navy"], True)
    s.line_shape(2.98, 2.03, 0.42, 0, PALETTE["teal"])
    s.line_shape(6.05, 2.03, 0.55, 0, PALETTE["teal"])
    s.line_shape(8.34, 2.03, 0.55, 0, PALETTE["teal"])
    s.box(1.05, 3.55, 2.15, 0.82, "Xác thực\nRFID + Face ID", PALETTE["white"], PALETTE["line"], 14)
    s.box(3.85, 3.55, 2.15, 0.82, "AI buồn ngủ\nEAR / PERCLOS", PALETTE["white"], PALETTE["line"], 14)
    s.box(6.65, 3.55, 2.15, 0.82, "EventBus\nWebSocket", PALETTE["white"], PALETTE["line"], 14)
    s.box(9.45, 3.55, 2.15, 0.82, "Dashboard\nSSE / SQLite", PALETTE["white"], PALETTE["line"], 14)
    s.line_shape(3.25, 3.96, 0.54, 0, PALETTE["line"])
    s.line_shape(6.05, 3.96, 0.54, 0, PALETTE["line"])
    s.line_shape(8.85, 3.96, 0.54, 0, PALETTE["line"])
    s.textbox(0.9, 5.35, 10.8, 0.45, "Ý chính khi nói: hệ thống tách thành thiết bị xử lý tại xe và trung tâm giám sát realtime, kết nối bằng WebSocket.", 16, PALETTE["muted"])
    slides.append(s)

    s = Slide("DrowsiGuard Edge Runtime", "Jetson-side")
    s.bullets(0.9, 1.55, 5.5, ["Chạy trên Jetson Nano, nhận dữ liệu từ camera, RFID, GPS.", "Điều phối phiên lái: chờ RFID, xác minh khuôn mặt, bắt đầu giám sát.", "Xử lý AI cục bộ để giảm phụ thuộc mạng.", "Phát cảnh báo tại xe bằng âm thanh / loa."], 17)
    s.box(7.0, 1.45, 4.8, 0.7, "Các vai trò chính", PALETTE["navy"], PALETTE["navy"], 18, PALETTE["white"], True)
    s.box(7.0, 2.35, 4.8, 0.58, "Thu thập dữ liệu cảm biến", PALETTE["white"], PALETTE["line"], 15)
    s.box(7.0, 3.08, 4.8, 0.58, "Phân tích khuôn mặt và trạng thái mắt", PALETTE["white"], PALETTE["line"], 15)
    s.box(7.0, 3.81, 4.8, 0.58, "Ra quyết định cảnh báo theo thời gian", PALETTE["white"], PALETTE["line"], 15)
    s.box(7.0, 4.54, 4.8, 0.58, "Đẩy sự kiện về Monitoring Hub", PALETTE["white"], PALETTE["line"], 15)
    slides.append(s)

    s = Slide("DrowsiGuard Monitoring Hub", "WebQuanLi")
    s.bullets(0.9, 1.55, 5.75, ["Cung cấp backend API, dashboard và lưu trữ dữ liệu.", "Nhận trạng thái thiết bị qua WebSocket.", "Đẩy cập nhật realtime ra trình duyệt bằng SSE.", "Quản lý tài xế, lịch sử phiên lái, cảnh báo và thống kê."], 17)
    s.box(7.1, 1.5, 4.75, 0.78, "Dashboard", PALETTE["mint"], PALETTE["teal"], 18, PALETTE["navy"], True)
    s.box(7.1, 2.55, 2.1, 0.68, "API", PALETTE["white"], PALETTE["line"], 16, PALETTE["ink"], True)
    s.box(9.75, 2.55, 2.1, 0.68, "SQLite", PALETTE["white"], PALETTE["line"], 16, PALETTE["ink"], True)
    s.box(7.1, 3.65, 2.1, 0.68, "WebSocket", PALETTE["white"], PALETTE["line"], 16, PALETTE["ink"], True)
    s.box(9.75, 3.65, 2.1, 0.68, "SSE", PALETTE["white"], PALETTE["line"], 16, PALETTE["ink"], True)
    s.textbox(7.2, 5.1, 4.4, 0.5, "Trong giao diện demo: tiêu đề hiển thị là Monitoring Hub, menu là Trung tâm giám sát.", 14, PALETTE["muted"])
    slides.append(s)

    s = Slide("Luồng demo nghiệp vụ", "RFID to monitoring")
    steps = ["Quét RFID", "Xác minh Face ID", "Mở phiên lái", "Giám sát AI", "Cảnh báo", "Lưu vết / hiển thị"]
    for i, text in enumerate(steps):
        x = 0.55 + i * 2.06
        s.box(x, 2.05, 1.62, 0.82, f"{i + 1}\n{text}", PALETTE["white"] if i % 2 else PALETTE["mint"], PALETTE["teal"], 13, PALETTE["ink"], True)
        if i < len(steps) - 1:
            s.line_shape(x + 1.67, 2.46, 0.32, 0, PALETTE["teal"])
    s.textbox(0.85, 4.1, 11.5, 0.48, "Điểm cần nhấn mạnh: RFID không tự động chứng minh danh tính tuyệt đối; Face ID giúp ràng buộc thẻ với đúng tài xế.", 17, PALETTE["ink"], True)
    s.bullets(1.0, 4.85, 10.8, ["Nếu xác minh thành công: hệ thống bắt đầu phiên lái và bật giám sát.", "Nếu thất bại hoặc mất kết nối: dashboard hiển thị trạng thái để người quản lý biết."], 16)
    slides.append(s)

    s = Slide("Pipeline AI phát hiện buồn ngủ", "Computer vision")
    items = [
        ("Frame camera", "Ảnh đầu vào"),
        ("Face Mesh", "Mốc khuôn mặt"),
        ("EAR / mắt", "Trạng thái mắt"),
        ("Temporal logic", "Tích lũy theo thời gian"),
        ("Alert level", "Cảnh báo"),
    ]
    for i, (head, sub) in enumerate(items):
        x = 0.72 + i * 2.45
        s.box(x, 1.95, 1.86, 0.88, f"{head}\n{sub}", PALETTE["blue"] if i % 2 else PALETTE["mint"], PALETTE["teal"], 14, PALETTE["navy"], True)
        if i < len(items) - 1:
            s.line_shape(x + 1.9, 2.4, 0.43, 0, PALETTE["teal"])
    s.box(0.9, 4.0, 5.35, 1.35, "Bản chất AI trong demo\n\nThị giác máy tính + luật thời gian, không phải mô hình deep learning nặng.", PALETTE["white"], PALETTE["line"], 16, PALETTE["ink"], True)
    s.box(6.95, 4.0, 5.25, 1.35, "Lý do phù hợp Jetson Nano\n\nNhẹ, chạy cục bộ, giải thích được và đủ ổn định cho demo đồ án.", PALETTE["white"], PALETTE["line"], 16, PALETTE["ink"], True)
    slides.append(s)

    s = Slide("Các chỉ số AI cần giải thích", "Metrics")
    s.box(0.82, 1.55, 2.8, 1.3, "EAR\nEye Aspect Ratio\n\nMắt càng nhắm, EAR càng giảm.", PALETTE["mint"], PALETTE["line"], 15, PALETTE["ink"], True)
    s.box(3.9, 1.55, 2.8, 1.3, "PERCLOS\n\nTỉ lệ thời gian mắt nhắm trong một cửa sổ thời gian.", PALETTE["blue"], PALETTE["line"], 15, PALETTE["ink"], True)
    s.box(6.98, 1.55, 2.8, 1.3, "Baseline\n\nMức mắt mở bình thường của từng người.", "FFFFFF", PALETTE["line"], 15, PALETTE["ink"], True)
    s.box(10.06, 1.55, 2.4, 1.3, "Debounce\n\nTránh cảnh báo vì nhiễu một frame.", "FDF7E7", "E5C669", 15, PALETTE["ink"], True)
    s.bullets(1.0, 3.7, 10.8, ["FPS camera: tốc độ lấy ảnh từ camera.", "FPS AI: số frame thật sự được xử lý bởi thuật toán, thường thấp hơn để tiết kiệm tài nguyên.", "Cảnh báo dựa trên trạng thái kéo dài theo thời gian, không dựa vào một ảnh đơn lẻ."], 17)
    slides.append(s)

    s = Slide("RFID, Face ID và phiên lái", "Identity")
    s.box(0.9, 1.65, 2.45, 0.8, "RFID\nđịnh danh thẻ", PALETTE["white"], PALETTE["teal"], 16, PALETTE["navy"], True)
    s.line_shape(3.42, 2.05, 0.55, 0, PALETTE["teal"])
    s.box(4.0, 1.65, 2.45, 0.8, "Face ID\nxác minh người", PALETTE["mint"], PALETTE["teal"], 16, PALETTE["navy"], True)
    s.line_shape(6.52, 2.05, 0.55, 0, PALETTE["teal"])
    s.box(7.1, 1.65, 2.45, 0.8, "Session\nphiên lái", PALETTE["blue"], PALETTE["teal"], 16, PALETTE["navy"], True)
    s.line_shape(9.62, 2.05, 0.55, 0, PALETTE["teal"])
    s.box(10.2, 1.65, 2.1, 0.8, "AI\nmonitor", "FDF7E7", "E5C669", 16, PALETTE["ink"], True)
    s.bullets(1.0, 3.25, 10.9, ["RFID giúp hệ thống biết tài xế dự kiến là ai.", "Face ID giảm rủi ro dùng nhầm hoặc dùng hộ thẻ.", "Session là đơn vị lưu lịch sử, cảnh báo, thời gian bắt đầu và kết thúc."], 18)
    slides.append(s)

    s = Slide("Realtime: WebSocket, EventBus, SSE", "Communication")
    s.box(0.8, 1.55, 2.35, 0.72, "Jetson Edge", PALETTE["mint"], PALETTE["teal"], 17, PALETTE["navy"], True)
    s.box(4.1, 1.55, 2.35, 0.72, "WebSocket", PALETTE["white"], PALETTE["line"], 17, PALETTE["ink"], True)
    s.box(7.4, 1.55, 2.35, 0.72, "EventBus", PALETTE["blue"], PALETTE["line"], 17, PALETTE["ink"], True)
    s.box(10.2, 1.55, 2.35, 0.72, "Browser SSE", PALETTE["white"], PALETTE["line"], 17, PALETTE["ink"], True)
    s.line_shape(3.2, 1.91, 0.82, 0, PALETTE["teal"])
    s.line_shape(6.5, 1.91, 0.82, 0, PALETTE["teal"])
    s.line_shape(9.8, 1.91, 0.32, 0, PALETTE["teal"])
    s.bullets(1.0, 3.3, 10.8, ["WebSocket dùng cho kênh Jetson gửi trạng thái và cảnh báo về server.", "EventBus gom sự kiện nội bộ để dashboard nhận cập nhật mới.", "SSE giúp trình duyệt tự nhận dữ liệu realtime mà không cần reload."], 17)
    s.textbox(1.0, 5.55, 10.8, 0.34, "Trong demo qua hai máy khác mạng, Tailscale giúp hai bên nhìn thấy nhau bằng IP riêng ổn định.", 16, PALETTE["muted"])
    slides.append(s)

    s = Slide("Database và dữ liệu lưu trữ", "Data")
    s.box(0.8, 1.52, 2.2, 0.75, "Drivers\nTài xế", PALETTE["white"], PALETTE["line"], 16, PALETTE["ink"], True)
    s.box(3.55, 1.52, 2.2, 0.75, "Sessions\nPhiên lái", PALETTE["mint"], PALETTE["teal"], 16, PALETTE["navy"], True)
    s.box(6.3, 1.52, 2.2, 0.75, "Alerts\nCảnh báo", PALETTE["white"], PALETTE["line"], 16, PALETTE["ink"], True)
    s.box(9.05, 1.52, 2.2, 0.75, "Stats\nThống kê", PALETTE["blue"], PALETTE["line"], 16, PALETTE["ink"], True)
    s.line_shape(3.05, 1.89, 0.45, 0, PALETTE["teal"])
    s.line_shape(5.8, 1.89, 0.45, 0, PALETTE["teal"])
    s.line_shape(8.55, 1.89, 0.45, 0, PALETTE["teal"])
    s.bullets(1.0, 3.15, 10.9, ["CSDL phục vụ quản lý và truy vết sau phiên lái.", "Dashboard không chỉ hiển thị realtime mà còn có lịch sử để đối chiếu.", "RFID được dùng như liên kết định danh tài xế trong dữ liệu."], 17)
    slides.append(s)

    s = Slide("Chịu lỗi mạng, GPS và phần cứng", "Reliability")
    s.box(0.8, 1.6, 3.35, 1.15, "Mất WebSocket\n\nJetson có thể buffer sự kiện và tự reconnect.", "FFF4F4", "D64545", 15, PALETTE["ink"], True)
    s.box(4.85, 1.6, 3.35, 1.15, "GPS\n\nTách rõ có dữ liệu NMEA và có fix vệ tinh.", "FDF7E7", "E5C669", 15, PALETTE["ink"], True)
    s.box(8.9, 1.6, 3.35, 1.15, "Thiết bị\n\nDashboard hiển thị trạng thái nguồn, camera, RFID, loa.", PALETTE["mint"], PALETTE["teal"], 15, PALETTE["ink"], True)
    s.bullets(1.0, 3.55, 10.85, ["Điểm mạnh demo: trạng thái lỗi được đưa lên màn hình quản lý thay vì im lặng.", "Tailscale được dùng để ổn định kết nối demo khi Jetson và laptop không cùng mạng LAN.", "GPS có thể cần thời gian bắt vệ tinh, không nên xem chưa fix là hỏng module."], 17)
    slides.append(s)

    s = Slide("Bảo mật và giới hạn demo", "Scope")
    s.box(0.85, 1.55, 5.2, 1.38, "Đã làm trong phạm vi đồ án\n\nRFID + Face ID, realtime monitoring, cảnh báo tại xe, lưu lịch sử.", PALETTE["mint"], PALETTE["line"], 16, PALETTE["ink"], True)
    s.box(6.85, 1.55, 5.2, 1.38, "Không trình bày quá mức\n\nOTA hiện nên xem là hướng mở rộng, không phải chức năng demo chính.", "FFF4F4", "D64545", 16, PALETTE["ink"], True)
    s.bullets(1.0, 3.55, 10.8, ["Khi hội đồng hỏi, cần phân biệt phần đã implement và phần dự kiến phát triển.", "Bảo mật demo tập trung ở xác minh danh tính tài xế và mạng riêng Tailscale.", "Các giới hạn còn lại: dữ liệu thử nghiệm nhỏ, ánh sáng/camera ảnh hưởng nhận diện, Jetson Nano tài nguyên hạn chế."], 16)
    slides.append(s)

    s = Slide("Kiểm thử và chứng minh", "Validation")
    s.box(0.8, 1.55, 3.25, 0.92, "Kiểm thử cảm biến\nRFID, camera, GPS, loa", PALETTE["white"], PALETTE["line"], 16, PALETTE["ink"], True)
    s.box(4.45, 1.55, 3.25, 0.92, "Kiểm thử realtime\nWebSocket, SSE, dashboard", PALETTE["mint"], PALETTE["teal"], 16, PALETTE["navy"], True)
    s.box(8.1, 1.55, 3.25, 0.92, "Kiểm thử nghiệp vụ\ncheck-in, session, alert", PALETTE["blue"], PALETTE["line"], 16, PALETTE["ink"], True)
    s.bullets(1.0, 3.15, 10.8, ["Demo nên đi theo kịch bản có kiểm soát: mở hub, mở Edge Runtime, quét RFID, xác minh, mô phỏng buồn ngủ.", "Các chỉ số cần quan sát: trạng thái kết nối, tài xế hiện tại, cảnh báo gần đây, vị trí GPS.", "Bằng chứng tốt nhất là vừa có log terminal vừa có dashboard đổi trạng thái."], 17)
    slides.append(s)

    s = Slide("Hạn chế và hướng phát triển", "Future work")
    s.box(0.85, 1.55, 5.25, 0.72, "Hạn chế hiện tại", PALETTE["navy"], PALETTE["navy"], 18, PALETTE["white"], True)
    s.bullets(1.0, 2.55, 5.1, ["Phụ thuộc điều kiện ánh sáng và góc camera.", "Tập dữ liệu kiểm thử còn nhỏ.", "Jetson Nano giới hạn tài nguyên.", "GPS trong nhà dễ chưa có fix."], 16)
    s.box(6.85, 1.55, 5.25, 0.72, "Hướng phát triển", PALETTE["teal"], PALETTE["teal"], 18, PALETTE["white"], True)
    s.bullets(7.0, 2.55, 5.1, ["Bổ sung mô hình học sâu khi có dữ liệu đủ lớn.", "Cải thiện xác thực khuôn mặt đa điều kiện.", "Thêm quản trị đội xe, phân quyền và báo cáo.", "Đóng gói triển khai và cập nhật an toàn hơn."], 16)
    slides.append(s)

    s = Slide("Kịch bản demo trước hội đồng", "Demo script")
    s.bullets(0.95, 1.55, 10.9, ["1. Mở DrowsiGuard Monitoring Hub, chỉ trạng thái ban đầu.", "2. Khởi động DrowsiGuard Edge Runtime trên Jetson Nano.", "3. Quét RFID, xác minh khuôn mặt và mở phiên lái.", "4. Cho camera thấy trạng thái bình thường rồi mô phỏng buồn ngủ.", "5. Chỉ cảnh báo realtime, lịch sử, vị trí GPS và trạng thái phần cứng.", "6. Kết luận: hệ thống xử lý tại xe và giám sát realtime ở trung tâm."], 17, gap=0.48)
    s.box(8.2, 5.55, 3.65, 0.72, "Chuẩn bị trước demo:\nkiểm tra IP Tailscale, camera, RFID, GPS, loa", "FDF7E7", "E5C669", 13, PALETTE["ink"], True)
    slides.append(s)

    s = Slide("Kết luận", "Closing", dark=True)
    s.textbox(0.9, 1.55, 10.9, 0.68, "DrowsiGuard chứng minh được một mô hình hệ thống cảnh báo buồn ngủ có thể chạy cục bộ trên Jetson Nano và giám sát realtime qua web.", 22, PALETTE["white"], True, valign="top")
    s.box(1.05, 3.15, 3.1, 1.0, "Nhận biết\nbuồn ngủ", PALETTE["teal"], "85E4D2", 20, PALETTE["white"], True)
    s.box(5.1, 3.15, 3.1, 1.0, "Cảnh báo\nkịp thời", "123047", "85E4D2", 20, PALETTE["white"], True)
    s.box(9.15, 3.15, 3.1, 1.0, "Giám sát\nrealtime", PALETTE["teal"], "85E4D2", 20, PALETTE["white"], True)
    s.textbox(0.9, 5.55, 10.9, 0.36, "Em xin cảm ơn thầy cô và hội đồng đã lắng nghe.", 20, "D8F0F5", True, align="ctr")
    slides.append(s)

    return slides


def write_pptx(slides: Iterable[Slide]) -> Path:
    slides = list(slides)
    if OUT.exists():
        OUT.unlink()

    pres_props, view_props, table_styles, master_rels, layout_rels, theme_xml = extra_props()
    with ZipFile(OUT, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types(len(slides)))
        z.writestr("_rels/.rels", root_rels())
        z.writestr("docProps/app.xml", app_xml(len(slides)))
        z.writestr("docProps/core.xml", core_xml())
        z.writestr("ppt/presentation.xml", presentation_xml(len(slides)))
        z.writestr("ppt/_rels/presentation.xml.rels", presentation_rels(len(slides)))
        z.writestr("ppt/presProps.xml", pres_props)
        z.writestr("ppt/viewProps.xml", view_props)
        z.writestr("ppt/tableStyles.xml", table_styles)
        z.writestr("ppt/slideMasters/slideMaster1.xml", slide_master())
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", master_rels)
        z.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout())
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", layout_rels)
        z.writestr("ppt/theme/theme1.xml", theme_xml)
        for idx, slide in enumerate(slides, start=1):
            z.writestr(f"ppt/slides/slide{idx}.xml", slide_xml(slide, idx))
            z.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", common_slide_rels())
    return OUT


if __name__ == "__main__":
    deck = write_pptx(build_slides())
    print(f"Created {deck}")
