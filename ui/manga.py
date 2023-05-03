# -*- coding: utf-8 -*-

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import os
import base64
import shutil
import json
from math import sqrt
#from PIL import Image, ImageDraw, ImageFont

import ui.static.icon
import utils.translater
import translator.ocr.dango
import translator.api
import utils.thread
import utils.message
import ui.progress_bar


DRAW_PATH = "./config/draw.jpg"
FONT_PATH_1 = "./config/other/NotoSansSC-Regular.otf"
FONT_PATH_2 = "./config/other/华康方圆体W7.TTC"


# 译文编辑界面
class TransEdit(QWidget) :

    def __init__(self, rate) :

        super(TransEdit, self).__init__()
        self.rate = rate
        self.ui()


    def ui(self) :

        # 窗口尺寸及不可拉伸
        self.window_width = int(500*self.rate)
        self.window_height = int(300*self.rate)
        self.resize(self.window_width, self.window_height)
        self.setMinimumSize(QSize(self.window_width, self.window_height))
        self.setMaximumSize(QSize(self.window_width, self.window_height))
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)

        # 窗口标题
        self.setWindowTitle("漫画翻译-译文编辑")
        # 窗口图标
        self.setWindowIcon(ui.static.icon.APP_LOGO_ICON)
        # 鼠标样式
        self.setCursor(ui.static.icon.PIXMAP_CURSOR)
        # 设置字体
        font_type = "华康方圆体W7"
        try :
            id = QFontDatabase.addApplicationFont(FONT_PATH_1)
            font_list = QFontDatabase.applicationFontFamilies(id)
            font_type = font_list[0]
        except Exception :
            pass
        self.setFont(QFont(font_type, 12))

        # 编辑框
        self.edit_text = QTextBrowser(self)
        self.customSetGeometry(self.edit_text, 0, 0, 500, 230)
        self.edit_text.setCursor(ui.static.icon.PIXMAP_CURSOR)
        self.edit_text.setReadOnly(False)

        # 确定按钮
        button = QPushButton(self)
        self.customSetGeometry(button, 125, 240, 100, 50)
        button.setText("重新贴字")
        button.clicked.connect(self.renderTextBlock)
        button.setCursor(ui.static.icon.SELECT_CURSOR)

        # 确定按钮
        button = QPushButton(self)
        self.customSetGeometry(button, 275, 240, 100, 50)
        button.setText("取消")
        button.clicked.connect(self.close)
        button.setCursor(ui.static.icon.SELECT_CURSOR)


    # 根据分辨率定义控件位置尺寸
    def customSetGeometry(self, object, x, y, w, h):

        object.setGeometry(QRect(int(x * self.rate),
                                 int(y * self.rate), int(w * self.rate),
                                 int(h * self.rate)))


    # 刷新翻译
    def renderTextBlock(self) :

        pass


# 根据文本块大小计算font_size
def getFontSize(coordinate, trans_text) :

    lines = []
    for val in coordinate :
        line = []
        line.append(val["upper_left"])
        line.append(val["upper_right"])
        line.append(val["lower_right"])
        line.append(val["lower_left"])
        lines.append(line)

    line_x = [j[0] for i in lines for j in i]
    line_y = [j[1] for i in lines for j in i]
    w = max(line_x) - min(line_x)
    h = max(line_y) - min(line_y)


    def get_structure(pts) :

        p1 = [int((pts[0][0] + pts[1][0]) / 2), int((pts[0][1] + pts[1][1]) / 2)]
        p2 = [int((pts[2][0] + pts[3][0]) / 2), int((pts[2][1] + pts[3][1]) / 2)]
        p3 = [int((pts[1][0] + pts[2][0]) / 2), int((pts[1][1] + pts[2][1]) / 2)]
        p4 = [int((pts[3][0] + pts[0][0]) / 2), int((pts[3][1] + pts[0][1]) / 2)]
        return [p1, p2, p3, p4]


    def get_font_size(pts) -> float :

        [l1a, l1b, l2a, l2b] = [a for a in get_structure(pts)]
        v1 = [l1b[0] - l1a[0], l1b[1] - l1a[1]]
        v2 = [l2b[0] - l2a[0], l2b[1] - l2a[1]]
        return min(sqrt(v2[0] ** 2 + v2[1] ** 2), sqrt(v1[0] ** 2 + v1[1] ** 2))


    def findNextPowerOf2(n) :

        i = 0
        while n != 0:
            i += 1
            n = n >> 1
        return 1 << i

    font_size = int(min([get_font_size(pts) for pts in lines]))
    text_mag_ratio = 1

    font_size_enlarged = findNextPowerOf2(font_size) * text_mag_ratio
    enlarge_ratio = font_size_enlarged / font_size
    font_size = font_size_enlarged

    while True:
        enlarged_w = round(enlarge_ratio * w)
        enlarged_h = round(enlarge_ratio * h)
        rows = enlarged_h // (font_size * 1.3)
        cols = enlarged_w // (font_size * 1.3)
        if rows * cols < len(trans_text) :
            enlarge_ratio *= 1.1
            continue
        break

    return int(font_size / enlarge_ratio)


# 渲染文本块
class RenderTextBlock(QWidget) :

    def __init__(self, rate, image_path, json_data, edit_window):
        super(RenderTextBlock, self).__init__()
        self.rate = rate
        self.image_path = image_path
        self.json_data = json_data
        self.trans_edit_ui = edit_window
        self.text_block_button_list = []
        self.ui()


    def ui(self) :

        # 窗口大小
        self.resize(1000*self.rate, 635*self.rate)
        # 窗口无标题栏、窗口置顶、窗口透明
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        # 鼠标样式
        self.setCursor(ui.static.icon.PIXMAP_CURSOR)

        # 图片大图展示
        scroll_area = QScrollArea(self)
        scroll_area.resize(self.width(), self.height())
        scroll_area.setWidgetResizable(True)
        image_label = QLabel(self)

        if self.json_data :
            # 渲染文本框
            # image = Image.open(self.image_path)
            # draw = ImageDraw.Draw(image)
            for text_block, trans_text in zip(self.json_data["text_block"], self.json_data["translated_text"]) :
                # trans_text = trans_text.replace(' ', '').replace('\t', '').replace('\n', '')
                # 计算文本坐标
                x = text_block["block_coordinate"]["upper_left"][0]
                y = text_block["block_coordinate"]["upper_left"][1]
                w = text_block["block_coordinate"]["lower_right"][0] - x
                h = text_block["block_coordinate"]["lower_right"][1] - y
                # 计算文字大小
                font_size = getFontSize(text_block["coordinate"], trans_text)
                # try :
                #     font_type = ImageFont.truetype(FONT_PATH_1, font_size)
                # except Exception :
                #     font_type = ImageFont.truetype(FONT_PATH_2, font_size)
                # 文本颜色
                font_color = tuple(text_block["foreground_color"])
                # 绘制矩形框
                button = QPushButton(image_label)
                button.setGeometry(x, y, w, h)
                button.setStyleSheet("QPushButton {background: transparent; border: 3px dashed red;}"
                                     "QPushButton:hover {background-color:rgba(62, 62, 62, 0.1)}")
                button.clicked.connect(lambda _, x=trans_text, y=font_color, z=font_size :
                                       self.clickTextBlock(x, y, z))

            #     # 取平均字高字宽
            #     font_width_sum, font_height_sum = 0, 0
            #     for char in trans_text :
            #         width, height = draw.textsize(char, font_type)
            #         font_width_sum += width
            #         font_height_sum += height
            #     font_width = round(font_width_sum / len(trans_text))
            #     font_height = round(font_height_sum / len(trans_text))
            #     # 计算文本总宽度、总高度
            #     max_width, max_height = self.getTextBlockSumSize((x, y, w, h), trans_text, font_width, font_height, draw, font_type)
            #     # 绘制文本
            #     text = ""
            #     sum_height = 0
            #     draw_x = x + w - (w - max_width) // 2 - font_width
            #     draw_y = y + (h - max_height) // 2
            #     for char in trans_text :
            #         text += char + "\n"
            #         sum_height += font_height
            #         text_width, text_height = draw.textsize(text, font=font_type)
            #         if text_height + font_height > h :
            #             #self.drawOutline(draw, draw_x, draw_y, text, font_type)
            #             draw.text((draw_x, draw_y), text, fill=font_color, font=font_type, direction=None)
            #             text = ""
            #             sum_height = 0
            #             draw_x = draw_x - font_width - 5
            #         elif char == trans_text[-1] :
            #             #self.drawOutline(draw, draw_x, draw_y, text, font_type)
            #             draw.text((draw_x, draw_y), text, fill=font_color, font=font_type, direction=None)
            # image.save(DRAW_PATH)
            # self.image_path = DRAW_PATH

        # 加载大图
        with open(self.image_path, "rb") as file:
            image = QImage.fromData(file.read())
        pixmap = QPixmap.fromImage(image)
        image_label.setPixmap(pixmap)
        image_label.resize(pixmap.width(), pixmap.height())
        scroll_area.setWidget(image_label)


    # 绘制轮廓
    def drawOutline(self, draw, draw_x, draw_y, text, font_type) :

        outline = 3
        for dx, dy in ((-outline, -outline), (-outline, outline), (outline, -outline), (outline, outline)) :
            draw.text((draw_x + dx, draw_y + dy), text, fill=(255, 255, 255), font=font_type, direction=None)


    # 计算文本总宽度、总高度
    def getTextBlockSumSize(self, rect, trans_text, font_width, font_height, draw, font_type) :

        x, y, w, h = rect[0], rect[1], rect[2], rect[3]
        text = ""
        sum_height = 0
        draw_x = x + w - font_width - 5
        max_width, max_height = 0, 0
        for char in trans_text :
            text += char + "\n"
            sum_height += font_height
            text_width, text_height = draw.textsize(text, font=font_type)
            if text_height + font_height > h :
                max_width += text_width
                if text_height > max_height :
                    max_height = text_height
                text = ""
                sum_height = 0
                draw_x = draw_x - font_width - 5
            elif char == trans_text[-1] :
                max_width += text_width
                if text_height > max_height :
                    max_height = text_height

        return max_width, max_height


    # 点击文本框
    def clickTextBlock(self, trans_text, font_color, font_size) :

        self.trans_edit_ui.edit_text.clear()
        # 计算文字大小
        self.trans_edit_ui.edit_text.setFontPointSize(font_size)
        # 文本颜色
        font_color = QColor(font_color[0], font_color[1], font_color[2])
        self.trans_edit_ui.edit_text.setTextColor(font_color)
        self.trans_edit_ui.edit_text.insertPlainText(trans_text)
        self.trans_edit_ui.show()


    # 获取图片的DPI大小
    def getImageDPI(self, px) :

        image = QImage(self.image_path)
        dpi_x = image.physicalDpiX()
        dpi_y = image.physicalDpiY()
        if dpi_x != dpi_y:
            width_inch = image.width() / dpi_x
            height_inch = image.height() / dpi_y
            dpi_x = image.width() / width_inch
            dpi_y = image.height() / height_inch
        pt = px * 72 / dpi_x

        return pt


# 自定义按键实现鼠标进入显示, 移出隐藏
class CustomButton(QPushButton) :

    def __init__(self, text) :
        super().__init__(text)
        self.setStyleSheet("background: transparent;")

    def enterEvent(self, a0) :
        self.setStyleSheet("background-color:rgba(62, 62, 62, 0.3)")
        self.show()
        return super().enterEvent(a0)

    def leaveEvent(self, a0) :
        self.setStyleSheet("background: transparent;")
        return super().leaveEvent(a0)


# 漫画翻译界面
class Manga(QWidget) :

    def __init__(self, object) :

        super(Manga, self).__init__()

        self.object = object
        self.logger = object.logger
        self.getInitConfig()
        self.ui()
        self.trans_edit_ui = TransEdit(self.rate)


    def ui(self) :

        # 窗口尺寸及不可拉伸
        self.resize(self.window_width, self.window_height)
        self.setMinimumSize(QSize(self.window_width, self.window_height))
        self.setWindowFlags(Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)

        # 窗口标题
        self.setWindowTitle("漫画翻译")
        # 窗口图标
        self.setWindowIcon(ui.static.icon.APP_LOGO_ICON)
        # 鼠标样式
        self.setCursor(ui.static.icon.PIXMAP_CURSOR)
        # 设置字体
        self.setStyleSheet("font: %spt '%s';"%(self.font_size, self.font_type))

        self.status_label = QLabel(self)
        self.customSetGeometry(self.status_label, 10, 670, 1200, 20)

        # 导入原图
        button = QPushButton(self)
        self.customSetGeometry(button, 0, 0, 120, 35)
        button.setText(" 导入原图")
        button.setStyleSheet("QPushButton {background: transparent;}"
                             "QPushButton:hover {background-color: #83AAF9;}"
                             "QPushButton:pressed {background-color: #4480F9;}")
        button.setIcon(ui.static.icon.OPEN_ICON)
        # 导入原图菜单
        self.input_menu = QMenu(button)
        self.input_action_group = QActionGroup(self.input_menu)
        self.input_action_group.setExclusive(True)
        self.createInputAction("从文件导入")
        self.createInputAction("从文件夹导入")
        # 将下拉菜单设置为按钮的菜单
        button.setMenu(self.input_menu)
        self.input_action_group.triggered.connect(self.openImageFiles)

        # 选择翻译源
        button = QPushButton(self)
        self.customSetGeometry(button, 120, 0, 120, 35)
        button.setText(" 选择翻译源")
        button.setStyleSheet("QPushButton {background: transparent;}"
                             "QPushButton:hover {background-color: #83AAF9;}"
                             "QPushButton:pressed {background-color: #4480F9;}")
        button.setIcon(ui.static.icon.TRANSLATE_ICON)
        # 翻译源菜单
        self.trans_menu = QMenu(button)
        self.trans_action_group = QActionGroup(self.trans_menu)
        self.trans_action_group.setExclusive(True)
        self.createTransAction("私人彩云")
        self.createTransAction("私人腾讯")
        self.createTransAction("私人百度")
        self.createTransAction("私人ChatGPT")
        # 将下拉菜单设置为按钮的菜单
        button.setMenu(self.trans_menu)
        self.trans_action_group.triggered.connect(self.changeSelectTrans)

        # 工具栏横向分割线
        self.createCutLine(0, 35, self.window_width, 1)

        # 原图按钮
        self.original_image_button = QPushButton(self)
        self.customSetGeometry(self.original_image_button, 0, 35, 66, 25)
        self.original_image_button.setText("原图")
        self.original_image_button.setStyleSheet("background-color: #83AAF9;")
        self.original_image_button.clicked.connect(lambda: self.clickImageButton("original"))

        # 原图按钮 和 译图按钮 竖向分割线
        self.createCutLine(67, 35, 1, 25)

        # 编辑按钮
        self.edit_image_button = QPushButton(self)
        self.customSetGeometry(self.edit_image_button, 67, 35, 66, 25)
        self.edit_image_button.setText("编辑")
        self.edit_image_button.setStyleSheet("QPushButton {background: transparent;}"
                                             "QPushButton:hover {background-color: #83AAF9;}")
        self.edit_image_button.clicked.connect(lambda: self.clickImageButton("edit"))

        # 原图按钮 和 译图按钮 竖向分割线
        self.createCutLine(134, 35, 1, 25)

        # 译图按钮
        self.trans_image_button = QPushButton(self)
        self.customSetGeometry(self.trans_image_button, 134, 35, 66, 25)
        self.trans_image_button.setText("译图")
        self.trans_image_button.setStyleSheet("QPushButton {background: transparent;}"
                                              "QPushButton:hover {background-color: #83AAF9;}")
        self.trans_image_button.clicked.connect(lambda: self.clickImageButton("trans"))

        # 译图右侧竖向分割线
        self.createCutLine(200, 35, 1, 25)

        # 原图列表框
        self.original_image_widget = QListWidget(self)
        self.customSetGeometry(self.original_image_widget, 0, 60, 200, 610)
        self.original_image_widget.setIconSize(QSize(180*self.rate, 180*self.rate))
        self.original_image_widget.itemSelectionChanged.connect(self.loadOriginalImage)
        self.original_image_widget.show()
        self.original_image_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.original_image_widget.customContextMenuRequested.connect(self.showOriginalListWidgetMenu)

        # 编辑图列表框
        self.edit_image_widget = QListWidget(self)
        self.customSetGeometry(self.edit_image_widget, 0, 60, 200, 610)
        self.edit_image_widget.setIconSize(QSize(180*self.rate, 180*self.rate))
        self.edit_image_widget.itemSelectionChanged.connect(self.loadEditImage)
        self.edit_image_widget.hide()
        self.edit_image_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.edit_image_widget.customContextMenuRequested.connect(self.showEditListWidgetMenu)

        # 译图列表框
        self.trans_image_widget = QListWidget(self)
        self.customSetGeometry(self.trans_image_widget, 0, 60, 200, 610)
        self.trans_image_widget.setIconSize(QSize(180*self.rate, 180*self.rate))
        self.trans_image_widget.itemSelectionChanged.connect(self.loadTransImage)
        self.trans_image_widget.hide()
        self.trans_image_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.trans_image_widget.customContextMenuRequested.connect(self.showTransListWidgetMenu)

        # 图片大图展示
        self.show_image_scroll_area = QScrollArea(self)
        self.customSetGeometry(self.show_image_scroll_area, 200, 35, 1000, 635)
        self.show_image_scroll_area.setWidgetResizable(True)

        # 底部横向分割线
        self.createCutLine(200, 670, self.window_width, 1)

        # 上一页按钮
        button = CustomButton(self)
        self.customSetGeometry(button, 200, 200, 50, 300)
        button.setIcon(ui.static.icon.LAST_PAGE_ICON)
        button.clicked.connect(lambda: self.changeImageListPosition("last"))

        # 下一页按钮
        button = CustomButton(self)
        self.customSetGeometry(button, 1130, 200, 50, 300)
        button.setIcon(ui.static.icon.NEXT_PAGE_ICON)
        button.clicked.connect(lambda: self.changeImageListPosition("next"))

        # 导入图片进度条
        self.input_images_progress_bar = ui.progress_bar.ProgressBar(self.object.yaml["screen_scale_rate"], "input_images")
        # 漫画翻译进度条
        self.trans_process_bar = ui.progress_bar.ProgressBar(self.object.yaml["screen_scale_rate"], "trans")


    # 初始化配置
    def getInitConfig(self):

        # 界面缩放比例
        self.rate = self.object.yaml["screen_scale_rate"]
        # 界面字体
        self.font_type = "华康方圆体W7"
        # 字体颜色
        self.color = "#595959"
        # 界面字体大小
        self.font_size = 10
        # 界面尺寸
        self.window_width = int(1200 * self.rate)
        self.window_height = int(700 * self.rate)
        # 图片路径列表
        self.image_path_list = []
        # 当前图片列表框的索引
        self.image_widget_index = 0
        # 当前图片列表框的滑块坐标
        self.image_widget_scroll_bar_value = 0
        # 渲染文本块的组件列表
        self.render_text_block_label = []


    # 根据分辨率定义控件位置尺寸
    def customSetGeometry(self, object, x, y, w, h):

        object.setGeometry(QRect(int(x * self.rate),
                                 int(y * self.rate), int(w * self.rate),
                                 int(h * self.rate)))


    # 绘制一条分割线
    def createCutLine(self, x, y, w, h) :

        label = QLabel(self)
        self.customSetGeometry(label, x, y, w, h)
        label.setFrameShadow(QFrame.Raised)
        label.setFrameShape(QFrame.Box)
        label.setStyleSheet("border-width: 1px; "
                            "border-style: solid; "
                            "border-color: rgba(62, 62, 62, 0.2);")


    # 上一页下一页按钮信号槽
    def changeImageListPosition(self, sign) :

        if len(self.image_path_list) == 0 :
            return

        image_widget = self.original_image_widget
        if self.edit_image_widget.isVisible() :
            image_widget = self.edit_image_widget
        elif self.trans_image_widget.isVisible() :
            image_widget = self.trans_image_widget

        row = image_widget.currentRow()
        if sign == "next" :
            if row < len(self.image_path_list) - 1 :
                image_widget.setCurrentRow(row + 1)
        else :
            if row > 0 :
                image_widget.setCurrentRow(row -1)


    # 打开图片文件列表
    def openImageFiles(self, action):

        dir_path = self.object.yaml.get("manga_dir_path", os.getcwd())
        options = QFileDialog.Options()
        images = []
        if action.data() == "从文件导入":
            images, _ = QFileDialog.getOpenFileNames(self,
                                                     "选择要翻译的生肉漫画原图（可多选）",
                                                     dir_path,
                                                     "图片类型(*.png *.jpg *.jpeg);;所有类型 (*)",
                                                     options=options)
            if not images :
                return

        elif action.data() == "从文件夹导入" :
            folder_path = QFileDialog.getExistingDirectory(self,
                                                           "选择要翻译的生肉漫画目录",
                                                           dir_path,
                                                           options=options)
            if not folder_path :
                return
            for file in os.listdir(folder_path) :
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext != ".png" and file_ext != ".jpg" and file_ext != ".jpeg" :
                    continue
                images.append(os.path.join(folder_path, file))
        else :
            return

        if images :
            # 清除所有图片
            self.clearAllImages()
            # 根据文件名排序
            images = self.dirFilesPathSort(images)
            # 进度条窗口
            self.input_images_progress_bar.modifyTitle("导入图片 -- 加载中请勿关闭此窗口")
            self.input_images_progress_bar.show()
            # 导入图片线程
            thread = utils.thread.createInputImagesQThread(self, images)
            thread.bar_signal.connect(self.input_images_progress_bar.paintProgressBar)
            thread.image_widget_signal.connect(self.inputImage)
            utils.thread.runQThread(thread)

        # 记忆上次操作的目录
        for image_path in images:
            self.object.yaml["manga_dir_path"] = os.path.dirname(image_path)
            break


    # 导入图片
    def inputImage(self, image_path, finish_sign) :

        if not finish_sign :
            # 图片添加至原图列表框
            self.originalImageWidgetAddImage(image_path)
            # 图片添加至编辑图列表框
            self.editImageWidgetAddImage()
            if os.path.exists(self.getIptFilePath(image_path)) :
                self.editImageWidgetRefreshImage(image_path)
            # 图片添加至译图列表框
            self.transImageWidgetAddImage()
            if os.path.exists(self.getRdrFilePath(image_path)) :
                self.transImageWidgetRefreshImage(image_path)

        else :
            # 跳转到原图栏
            self.original_image_button.click()
            self.original_image_widget.setCurrentRow(0)
            self.loadOriginalImage()
            self.input_images_progress_bar.close()


    # 文件列表排序
    def dirFilesPathSort(self, files) :

        tmp_dict = {}
        for file_path in files :
            if len(file_path) not in tmp_dict :
                tmp_dict[len(file_path)] = []
            tmp_dict[len(file_path)].append(file_path)

        new_files = []
        for k in sorted(tmp_dict.keys()) :
            for val in sorted(tmp_dict[k]) :
                new_files.append(val)

        return new_files


    # 清除所有图片
    def clearAllImages(self) :

        self.original_image_widget.clear()
        self.edit_image_widget.clear()
        self.trans_image_widget.clear()
        self.image_path_list.clear()


    # 点击 原图/编辑/译图 按钮
    def clickImageButton(self, button_type):

        self.original_image_widget.hide()
        self.edit_image_widget.hide()
        self.trans_image_widget.hide()
        self.original_image_button.setStyleSheet("QPushButton {background: transparent;}"
                                                 "QPushButton:hover {background-color: #83AAF9;}")
        self.edit_image_button.setStyleSheet("QPushButton {background: transparent;}"
                                             "QPushButton:hover {background-color: #83AAF9;}")
        self.trans_image_button.setStyleSheet("QPushButton {background: transparent;}"
                                              "QPushButton:hover {background-color: #83AAF9;}")
        if button_type == "original":
            self.original_image_widget.show()
            self.original_image_button.setStyleSheet("background-color: #83AAF9;")
            self.original_image_widget.verticalScrollBar().setValue(self.image_widget_scroll_bar_value)
            self.original_image_widget.setCurrentRow(self.image_widget_index)
            self.loadOriginalImage()

        elif button_type == "edit":
            self.edit_image_widget.show()
            self.edit_image_button.setStyleSheet("background-color: #83AAF9;")
            self.edit_image_widget.verticalScrollBar().setValue(self.image_widget_scroll_bar_value)
            self.edit_image_widget.setCurrentRow(self.image_widget_index)
            self.loadEditImage()

        elif button_type == "trans":
            self.trans_image_widget.show()
            self.trans_image_button.setStyleSheet("background-color: #83AAF9;")
            self.trans_image_widget.verticalScrollBar().setValue(self.image_widget_scroll_bar_value)
            self.trans_image_widget.setCurrentRow(self.image_widget_index)
            self.loadTransImage()


    # 创建导入原图按钮的下拉菜单
    def createInputAction(self, label):

        action = QAction(label, self.input_menu)
        action.setCheckable(True)
        action.setData(label)
        self.input_action_group.addAction(action)
        self.input_menu.addAction(action)


    # 创建翻译源按钮的下拉菜单
    def createTransAction(self, label) :

        action = QAction(label, self.trans_menu)
        action.setCheckable(True)
        action.setData(label)
        self.trans_action_group.addAction(action)
        self.trans_menu.addAction(action)
        if self.object.config["mangaTrans"] == label :
            action.setChecked(True)
            self.status_label.setText("正在使用: {}".format(label))


    # 改变所使用的翻译源
    def changeSelectTrans(self, action) :

        self.object.config["mangaTrans"] = action.data()
        self.status_label.setText("正在使用: {}".format(action.data()))


    # 设置原图列表框右键菜单
    def showOriginalListWidgetMenu(self, pos) :

        item = self.original_image_widget.itemAt(pos)
        if item is not None:
            menu = QMenu(self)
            # 添加菜单项
            translater_action = menu.addAction("翻译")
            translater_action.triggered.connect(lambda: self.translaterItemWidget(item))
            delete_action = menu.addAction("移除")
            delete_action.triggered.connect(lambda: self.removeItemWidget(item))
            # 显示菜单
            cursorPos = QCursor.pos()
            menu.exec_(cursorPos)


    # 设置编辑图列表框右键菜单
    def showEditListWidgetMenu(self, pos):

        item = self.edit_image_widget.itemAt(pos)
        if item is not None:
            menu = QMenu(self)
            # 添加菜单项
            rdr_action = menu.addAction("重新渲染翻译结果")
            # rdr_action.triggered.connect(lambda: self.saveImageItemWidget(item))
            # 显示菜单
            cursorPos = QCursor.pos()
            menu.exec_(cursorPos)


    # 设置译图列表框右键菜单
    def showTransListWidgetMenu(self, pos):

        item = self.trans_image_widget.itemAt(pos)
        if item is not None:
            menu = QMenu(self)
            # 添加菜单项
            output_action = menu.addAction("另存为")
            output_action.triggered.connect(lambda: self.saveImageItemWidget(item))
            # 显示菜单
            cursorPos = QCursor.pos()
            menu.exec_(cursorPos)


    # 译图框保存图片
    def saveImageItemWidget(self, item) :

        row = self.trans_image_widget.indexFromItem(item).row()
        image_path = self.image_path_list[row]

        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self,
                                                   "译图另存为",
                                                   image_path,
                                                   "图片类型(*.png *.jpg *.jpeg);;所有类型 (*)",
                                                   options=options)
        if file_path :
            shutil.copy(self.getRdrFilePath(image_path), file_path)


    # 列表框右键菜单删除子项
    def removeItemWidget(self, item) :

        row = self.original_image_widget.indexFromItem(item).row()
        if row > (len(self.image_path_list) - 1) :
            return
        # 列表框删除图片
        self.original_image_widget.takeItem(row)
        self.edit_image_widget.takeItem(row)
        self.trans_image_widget.takeItem(row)
        self.image_path_list.pop(row)


    # 原图列表框添加图片
    def originalImageWidgetAddImage(self, image_path):

        item = QListWidgetItem(image_path, self.original_image_widget)
        pixmap = QPixmap(image_path)
        pixmap = pixmap.scaled(180*self.rate, 180*self.rate, aspectRatioMode=Qt.KeepAspectRatio)
        item.setIcon(QIcon(pixmap))
        item.setText(os.path.basename(image_path))
        self.original_image_widget.addItem(item)
        self.image_path_list.append(image_path)


    # 编辑图列表框添加图片
    def editImageWidgetAddImage(self) :

        item = QListWidgetItem("翻译后生成", self.edit_image_widget)
        item.setSizeHint(QSize(0, 100*self.rate))
        self.edit_image_widget.addItem(item)


    # 译图列表框添加图片
    def transImageWidgetAddImage(self) :

        item = QListWidgetItem("翻译后生成", self.trans_image_widget)
        item.setSizeHint(QSize(0, 100*self.rate))
        self.trans_image_widget.addItem(item)


    # 刷新编辑图列表框内item的图片
    def editImageWidgetRefreshImage(self, image_path) :

        if image_path not in self.image_path_list :
            return
        row = self.image_path_list.index(image_path)
        item = self.edit_image_widget.item(row)
        ipt_image_path = self.getIptFilePath(image_path)
        pixmap = QPixmap(ipt_image_path)
        pixmap = pixmap.scaled(180*self.rate, 180*self.rate, aspectRatioMode=Qt.KeepAspectRatio)
        item.setIcon(QIcon(pixmap))
        item.setText(os.path.basename(image_path))


    # 刷新译图列表框内item的图片
    def transImageWidgetRefreshImage(self, image_path):

        if image_path not in self.image_path_list :
            return
        row = self.image_path_list.index(image_path)
        item = self.trans_image_widget.item(row)
        rdr_image_path = self.getRdrFilePath(image_path)
        pixmap = QPixmap(rdr_image_path)
        pixmap = pixmap.scaled(180*self.rate, 180*self.rate, aspectRatioMode=Qt.KeepAspectRatio)
        item.setIcon(QIcon(pixmap))
        item.setText(os.path.basename(image_path))


    # 展示原图图片大图
    def loadOriginalImage(self) :

        index = self.original_image_widget.currentRow()
        if index >= 0 and index < len(self.image_path_list) :
            image_path = self.image_path_list[index]
            self.renderImageAndTextBlock(image_path, "original")
            self.image_widget_index = index
            self.image_widget_scroll_bar_value = self.original_image_widget.verticalScrollBar().value()


    # 展示编辑图图片大图
    def loadEditImage(self) :

        index = self.edit_image_widget.currentRow()
        if index >= 0 and index < len(self.image_path_list):
            image_path = self.image_path_list[index]
            ipt_image_path = self.getIptFilePath(image_path)
            if os.path.exists(ipt_image_path) :
                self.renderImageAndTextBlock(image_path, "edit")
            else :
                self.show_image_scroll_area.hide()
            self.image_widget_index = index
            self.image_widget_scroll_bar_value = self.edit_image_widget.verticalScrollBar().value()


    # 展示译图图片大图
    def loadTransImage(self):

        index = self.trans_image_widget.currentRow()
        if index >= 0 and index < len(self.image_path_list) :
            image_path = self.image_path_list[index]
            rdr_image_path = self.getRdrFilePath(image_path)
            if os.path.exists(rdr_image_path) :
                self.renderImageAndTextBlock(image_path, "trans")
            else :
                self.show_image_scroll_area.hide()
            self.image_widget_index = index
            self.image_widget_scroll_bar_value = self.trans_image_widget.verticalScrollBar().value()


    # 翻译进程
    def transProcess(self, image_path, reload_sign=False) :

        # 漫画OCR
        if not os.path.exists(self.getJsonFilePath(image_path)) or reload_sign :
            sign, ocr_result = self.mangaOCR(image_path)
            if not sign:
                return utils.message.MessageBox("OCR过程失败", ocr_result, self.rate)

        # 翻译
        trans_sign = False
        if not os.path.exists(self.getJsonFilePath(image_path)) or reload_sign :
            trans_sign = True
        else:
            with open(self.getJsonFilePath(image_path), "r", encoding="utf-8") as file:
                json_data = json.load(file)
            if "translated_text" not in json_data:
                trans_sign = True
        if trans_sign :
            sign, trans_result = self.mangaTrans(image_path)
            if not sign:
                return utils.message.MessageBox("翻译过程失败", trans_result, self.rate)

        # 文字消除
        if not os.path.exists(self.getIptFilePath(image_path)) or reload_sign :
            sign, ipt_result = self.mangaTextInpaint(image_path)
            if not sign :
                return utils.message.MessageBox("文字消除过程失败", ipt_result, self.rate)
            # 消除好的图片加入编辑图列表框
            self.editImageWidgetRefreshImage(image_path)

        # 漫画文字渲染
        if not os.path.exists(self.getRdrFilePath(image_path)) or reload_sign :
            sign, rdr_result = self.mangaTextRdr(image_path)
            if not sign:
                return utils.message.MessageBox("文字渲染过程失败", rdr_result, self.rate)
            # 渲染好的图片加入译图列表框
            self.transImageWidgetRefreshImage(image_path)


    # 单图翻译
    def translaterItemWidget(self, item) :

        # 校验是否选择了翻译源
        if not self.object.config["mangaTrans"] :
            return utils.message.MessageBox("翻译失败", "请先选择要使用的翻译源     ", self.rate)
        # 获取图片路径
        row = self.original_image_widget.indexFromItem(item).row()
        image_path = self.image_path_list[row]
        image_paths = []
        image_paths.append(image_path)
        # 进度条窗口
        self.trans_process_bar.modifyTitle("漫画翻译 -- 执行中请勿关闭此窗口")
        self.trans_process_bar.show()
        # 创建执行线程
        reload_sign = True
        thread = utils.thread.createMangaTransQThread(self, image_paths, reload_sign)
        thread.signal.connect(self.finishTransProcessRefresh)
        thread.bar_signal.connect(self.trans_process_bar.paintProgressBar)
        utils.thread.runQThread(thread)


    # 漫画OCR
    def mangaOCR(self, image_path) :

        sign, result = translator.ocr.dango.mangaOCR(self.object, image_path)
        if sign :
            # 缓存mask图片
            with open(self.getMaskFilePath(image_path), "wb") as file :
                file.write(base64.b64decode(result["mask"]))
            del result["mask"]
            # 缓存ocr结果
            with open(self.getJsonFilePath(image_path), "w", encoding="utf-8") as file:
                json.dump(result, file, indent=4)

        return sign, result


    # 漫画文字消除
    def mangaTextInpaint(self, image_path) :

        # 从缓存文件里获取mask图片
        with open(self.getMaskFilePath(image_path), "rb") as file:
            mask = base64.b64encode(file.read()).decode("utf-8")
        # 请求漫画ipt
        sign, result = translator.ocr.dango.mangaIPT(self.object, image_path, mask)
        if sign :
            # 缓存inpaint图片
            with open(self.getIptFilePath(image_path), "wb") as file :
                file.write(base64.b64decode(result["inpainted_image"]))

        return sign, result


    # 漫画翻译
    def mangaTrans(self, image_path) :

        # 从缓存文件中获取json结果
        with open(self.getJsonFilePath(image_path), "r", encoding="utf-8") as file:
            json_data = json.load(file)
        # 翻译源
        manga_trans = self.object.config["mangaTrans"]
        # 存译文列表
        translated_text = []
        # 解析ocr结果获取原文
        original = []
        for val in json_data["text_block"] :
            tmp = ""
            for text in val["texts"]:
                tmp += text
            original.append(tmp)
        original = "\n".join(original)

        # 调用翻译
        result = ""
        if manga_trans == "私人彩云" :
            result = translator.api.caiyun(sentence=original,
                                           token=self.object.config["caiyunAPI"],
                                           logger=self.logger)
        elif manga_trans == "私人腾讯" :
            result = translator.api.tencent(sentence=original,
                                            secret_id=self.object.config["tencentAPI"]["Key"],
                                            secret_key=self.object.config["tencentAPI"]["Secret"],
                                            logger=self.logger)
        elif manga_trans == "私人百度" :
            result = translator.api.baidu(sentence=original,
                                          app_id=self.object.config["baiduAPI"]["Key"],
                                          secret_key=self.object.config["baiduAPI"]["Secret"],
                                          logger=self.logger)
        elif manga_trans == "私人ChatGPT" :
            result = translator.api.chatgpt(api_key=self.object.config["chatgptAPI"],
                                            language=self.object.config["language"],
                                            proxy=self.object.config["chatgptProxy"],
                                            content=self.object.translation_ui.original,
                                            logger=self.logger)

        for index, word in enumerate(result.split("\n")[:len(json_data["text_block"])]) :
            translated_text.append(word)

        json_data["translated_text"] = translated_text
        # 缓存ocr结果
        with open(self.getJsonFilePath(image_path), "w", encoding="utf-8") as file :
            json.dump(json_data, file, indent=4)

        # @TODO 缺少错误处理
        return True, result


    # 漫画文字渲染
    def mangaTextRdr(self, image_path):

        # 从缓存文件中获取json结果
        with open(self.getJsonFilePath(image_path), "r", encoding="utf-8") as file :
            json_data = json.load(file)
        # 从缓存文件里获取mask图片
        with open(self.getMaskFilePath(image_path), "rb") as file :
            mask = base64.b64encode(file.read()).decode("utf-8")
        # 从缓存文件里获取ipt图片
        with open(self.getIptFilePath(image_path), "rb") as file :
            ipt = base64.b64encode(file.read()).decode("utf-8")
        # 漫画rdr
        sign, result = translator.ocr.dango.mangaRDR(
            object=self.object,
            mask=mask,
            trans_list=json_data["translated_text"],
            inpainted_image=ipt,
            text_block=json_data["text_block"]
        )
        if sign :
            # 缓存inpaint图片
            with open(self.getRdrFilePath(image_path), "wb") as file :
                file.write(base64.b64decode(result["rendered_image"]))

        return sign, result


    # 获取工作目录
    def getDangoMangaPath(self, image_path) :

        # 获取漫画翻译缓存目录
        base_path = os.path.dirname(image_path)
        dango_manga_path = os.path.join(base_path, "dango_manga")
        # 如果目录不存在就创建工作缓存目录
        if not os.path.exists(dango_manga_path) :
            os.mkdir(dango_manga_path)
        # 如果目录不存在就创建工作缓存目录
        tmp_path = os.path.join(dango_manga_path, "tmp")
        if not os.path.exists(tmp_path) :
            os.mkdir(tmp_path)
        # 获取不带拓展名的文件名
        file_name = os.path.splitext(os.path.basename(image_path))[0]

        return dango_manga_path, file_name


    # 获取某张图对应的Json结果文件缓存路径
    def getJsonFilePath(self, image_path) :

        dango_manga_path, file_name = self.getDangoMangaPath(image_path)
        tmp_path = os.path.join(dango_manga_path, "tmp")
        file_path = os.path.join(tmp_path, "{}.json".format(file_name))

        return file_path


    # 获取某张图对应的mask结果文件缓存路径
    def getMaskFilePath(self, image_path) :

        dango_manga_path, file_name = self.getDangoMangaPath(image_path)
        tmp_path = os.path.join(dango_manga_path, "tmp")
        file_path = os.path.join(tmp_path, "{}_mask.png".format(file_name))

        return file_path


    # 获取某张图对应的文字消除结果文件缓存路径
    def getIptFilePath(self, image_path) :

        dango_manga_path, file_name = self.getDangoMangaPath(image_path)
        tmp_path = os.path.join(dango_manga_path, "tmp")
        file_path = os.path.join(tmp_path, "{}_ipt.png".format(file_name))

        return file_path


    # 获取某张图对应的文字渲染结果文件缓存路径
    def getRdrFilePath(self, image_path) :

        dango_manga_path, file_name = self.getDangoMangaPath(image_path)
        file_path = os.path.join(dango_manga_path, "{}.png".format(file_name))

        return file_path


    # 渲染图片和文本块
    def renderImageAndTextBlock(self, image_path, show_type) :

        if show_type == "original" :
            json_data = None
        elif show_type == "edit" :
            with open(self.getJsonFilePath(image_path), "r", encoding="utf-8") as file:
                json_data = json.load(file)
            image_path = self.getRdrFilePath(image_path)
        elif show_type == "trans" :
            image_path = self.getRdrFilePath(image_path)
            json_data = None
        else :
            return

        self.show_image_scroll_area.setWidget(None)
        widget = RenderTextBlock(
            rate=self.rate,
            image_path=image_path,
            json_data=json_data,
            edit_window=self.trans_edit_ui
        )
        self.show_image_scroll_area.setWidget(widget)
        self.show_image_scroll_area.show()


    # 翻译完成后刷新译图栏
    def finishTransProcessRefresh(self, value, signal) :

        if signal :
            self.trans_image_button.click()
            row = self.image_path_list.index(value)
            self.trans_image_widget.setCurrentRow(row)
            self.loadTransImage()
        else :
            if value :
                # @TODO 缺少错误处理
                pass
            self.trans_process_bar.close()


    # 窗口关闭处理
    def closeEvent(self, event) :

        self.hide()
        self.object.translation_ui.show()
        if self.object.range_ui.show_sign == True:
            self.object.range_ui.show()