# -*- coding: utf-8 -*-
"""生成课表导入模版：模版.xlsx（标准工作簿）+ 模版.xls（SpreadsheetML，UTF-8，多 sheet）。

两种文件内容一致：第 1 行表头，第 2 行起「第一节课…第十四节课」，每个 sheet 一周。
"""
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

OUT_DIR = r"D:\ai\bff\whale-pet"
DAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
PERIODS = [
    (1, "08:30", "09:15"), (2, "09:20", "10:05"), (3, "10:20", "11:05"),
    (4, "11:10", "11:55"), (5, "12:10", "12:55"), (6, "13:00", "13:45"),
    (7, "13:50", "14:35"), (8, "14:45", "15:30"), (9, "15:35", "16:20"),
    (10, "16:25", "17:10"), (11, "17:20", "18:05"), (12, "18:10", "18:55"),
    (13, "19:05", "19:50"), (14, "19:55", "20:40"),
]
WEEKS = list(range(1, 9))


def period_label(p):
    cn = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
          "十一", "十二", "十三", "十四"]
    return f"第{cn[p - 1]}节课"


def build_xlsx(path):
    wb = Workbook()
    wb.remove(wb.active)
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for week in WEEKS:
        ws = wb.create_sheet(f"第{week}周")
        ws.append(["节次", "上课时间"] + DAYS)
        for cell in ws[1]:
            cell.font = Font(name="微软雅黑", size=10.5, bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="2F5597")
            cell.alignment = center
            cell.border = border
        for p, start, end in PERIODS:
            ws.append([period_label(p), f"{start}-{end}"] + [""] * 7)
        for row in ws.iter_rows(min_row=2, max_row=15, max_col=9):
            for cell in row:
                cell.border = border
                cell.alignment = center
                if cell.column <= 2:
                    cell.fill = PatternFill("solid", fgColor="F2F2F2")
        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 13
        for i in range(7):
            ws.column_dimensions[chr(ord("C") + i)].width = 22
        ws.freeze_panes = "C2"
        ws.row_dimensions[1].height = 24

    ws = wb.create_sheet("填写说明")
    tips = [
        ("怎么填", "一格 = 一节课。单元格里写三行：课名 / 教室 / 教师（Excel 里按 Alt+Enter 换行）。"),
        ("只写课名也行", "教室、教师可以留空；留空的部分不会瞎猜。"),
        ("周次", "每个 sheet 名就是周次，写成「第3周」或「3」都认。"),
        ("节次", "从第二行开始依次是第一节到第十四节，别插空行、别改顺序。"),
        ("时间", "第二列已经填好作息时间；学校不同就整列改掉。"),
        ("周次范围", "比如某门课只上 5-18 周、或者单双周，请在课名后面自己注明，宠物会按周表分开显示。"),
        ("导入", "桌宠右键 → 导入课表… → 选这个文件 → 填「今天是第几周」。"),
    ]
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 80
    for i, (k, v) in enumerate(tips, start=1):
        a = ws.cell(row=i, column=1, value=k)
        a.font = Font(name="微软雅黑", size=10, bold=True, color="2F5597")
        b = ws.cell(row=i, column=2, value=v)
        b.font = Font(name="微软雅黑", size=10)
        b.alignment = Alignment(wrap_text=True, vertical="center")

    wb.save(path)
    print("saved", path)


def build_xls(path):
    """SpreadsheetML 2003：UTF-8 XML，Excel 直接认，多 worksheet。"""
    def cell(value, style=None):
        st = f' ss:StyleID="{style}"' if style else ""
        text = (value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f'<Cell{st}><Data ss:Type="String">{text}</Data></Cell>'

    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<?mso-application progid="Excel.Sheet"?>',
             '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"',
             ' xmlns:o="urn:schemas-microsoft-com:office:office"',
             ' xmlns:x="urn:schemas-microsoft-com:office:excel"',
             ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">',
             '<Styles>',
             '<Style ss:ID="head"><Font ss:Bold="1" ss:Color="#FFFFFF"/>'
             '<Interior ss:Color="#2F5597" ss:Pattern="Solid"/>'
             '<Alignment ss:Horizontal="Center" ss:Vertical="Center"/></Style>',
             '<Style ss:ID="time"><Interior ss:Color="#F2F2F2" ss:Pattern="Solid"/>'
             '<Alignment ss:Horizontal="Center" ss:Vertical="Center"/></Style>',
             '<Style ss:ID="day"><Alignment ss:Horizontal="Center" ss:Vertical="Center" '
             'ss:WrapText="1"/></Style>',
             '</Styles>']

    for week in WEEKS:
        parts.append(f'<Worksheet ss:Name="第{week}周"><Table>')
        parts.append('<Column ss:Width="88"/><Column ss:Width="96"/>')
        parts.append('<Column ss:Width="150"/><Column ss:Width="150"/><Column ss:Width="150"/>'
                     '<Column ss:Width="150"/><Column ss:Width="150"/><Column ss:Width="150"/>'
                     '<Column ss:Width="150"/>')
        parts.append('<Row ss:Height="22">')
        parts.append(cell("节次", "head") + cell("上课时间", "head"))
        parts.extend(cell(d, "head") for d in DAYS)
        parts.append('</Row>')
        for p, start, end in PERIODS:
            parts.append('<Row ss:Height="26">')
            parts.append(cell(period_label(p), "time") + cell(f"{start}-{end}", "time"))
            parts.extend(cell("", "day") for _ in DAYS)
            parts.append('</Row>')
        parts.append('</Table></Worksheet>')

    parts.append('<Worksheet ss:Name="填写说明"><Table>')
    parts.append('<Column ss:Width="110"/><Column ss:Width="520"/>')
    tips = [
        ("怎么填", "一格 = 一节课；单元格里写三行：课名 / 教室 / 教师（Alt+Enter 换行）。"),
        ("周次", "每个 sheet 名就是周次，写「第3周」或「3」都认。"),
        ("节次", "从第二行起依次第一节到第十四节，别插空行。"),
        ("时间", "第二列是作息时间，学校不同就整列改。"),
        ("导入", "桌宠右键 → 导入课表… → 选文件 → 告诉它今天是第几周。"),
    ]
    for k, v in tips:
        parts.append('<Row>' + cell(k, "time") + cell(v, "day") + '</Row>')
    parts.append('</Table></Worksheet>')
    parts.append('</Workbook>')

    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("".join(parts))
    print("saved", path)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    build_xlsx(os.path.join(OUT_DIR, "模版.xlsx"))
    build_xls(os.path.join(OUT_DIR, "模版.xls"))
