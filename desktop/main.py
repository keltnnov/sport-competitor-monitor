"""
Мониторинг конкурентов - Desktop приложение на PyQt6
"""
import sys
import os
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QFrame, QScrollArea,
    QFileDialog, QStackedWidget, QSplitter, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QFont, QIcon, QDragEnterEvent, QDropEvent

from styles import DARK_THEME
from api_client import api_client


class WorkerThread(QThread):
    """Поток для выполнения API запросов"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DropZone(QFrame):
    """Зона для drag & drop изображений"""
    fileDropped = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setObjectName("uploadZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(200)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.icon_label = QLabel("📁")
        self.icon_label.setStyleSheet("font-size: 48px;")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.text_label = QLabel("Перетащите изображение или нажмите для выбора")
        self.text_label.setStyleSheet("color: #94a3b8; font-size: 14px;")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.hint_label = QLabel("PNG, JPG, GIF, WEBP до 10MB")
        self.hint_label.setStyleSheet("color: #64748b; font-size: 12px;")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.hide()
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.preview_label)
        
        self.selected_file = None
    
    def mousePressEvent(self, event):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите изображение",
            "",
            "Изображения (*.png *.jpg *.jpeg *.gif *.webp)"
        )
        if file_path:
            self.set_file(file_path)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("QFrame#uploadZone { border-color: #06b6d4; background-color: rgba(6, 182, 212, 0.1); }")
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("")
    
    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("")
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                self.set_file(file_path)
    
    def set_file(self, file_path: str):
        self.selected_file = file_path
        
        # Показываем превью
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(300, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.preview_label.setPixmap(pixmap)
            self.preview_label.show()
            self.icon_label.hide()
            self.text_label.setText(Path(file_path).name)
            self.hint_label.setText("Нажмите для замены")
        
        self.fileDropped.emit(file_path)
    
    def clear(self):
        self.selected_file = None
        self.preview_label.hide()
        self.icon_label.show()
        self.text_label.setText("Перетащите изображение или нажмите для выбора")
        self.hint_label.setText("PNG, JPG, GIF, WEBP до 10MB")


class ResultBlock(QFrame):
    """Блок результата анализа"""
    def __init__(self, title: str, items: list, icon: str = "→"):
        super().__init__()
        self.setObjectName("resultBlock")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        
        for item in items:
            item_label = QLabel(f"{icon} {item}")
            item_label.setWordWrap(True)
            item_label.setStyleSheet("color: #94a3b8; margin-left: 8px; line-height: 1.5;")
            layout.addWidget(item_label)


class ScoreBlock(QFrame):
    """Блок числовой оценки 0-10 с полосой"""
    def __init__(self, title: str, score: int):
        super().__init__()
        self.setObjectName("resultBlock")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")

        value_label = QLabel(f"{score}/10")
        value_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #22d3ee;")

        bar = QProgressBar()
        bar.setRange(0, 10)
        bar.setValue(score)
        bar.setTextVisible(False)
        bar.setFixedHeight(8)

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(bar)


class TextBlock(QFrame):
    """Блок с заголовком и абзацем текста"""
    def __init__(self, title: str, text: str):
        super().__init__()
        self.setObjectName("resultBlock")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")

        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setStyleSheet("color: #94a3b8;")

        layout.addWidget(title_label)
        layout.addWidget(text_label)


class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Мониторинг конкурентов | AI Ассистент")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # Применяем стили
        self.setStyleSheet(DARK_THEME)
        
        # Главный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        self.setup_sidebar(main_layout)
        
        # Content area
        self.setup_content(main_layout)
        
        # Текущий worker
        self.current_worker = None
        
        # Проверяем подключение к серверу
        self.check_server_connection()
    
    def setup_sidebar(self, parent_layout):
        """Создание боковой панели"""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(280)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Logo
        logo = QLabel("⚡ CompetitorAI")
        logo.setObjectName("logo")
        layout.addWidget(logo)
        
        # Navigation
        nav_widget = QWidget()
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(12, 16, 12, 16)
        nav_layout.setSpacing(4)
        
        self.nav_buttons = []
        nav_items = [
            ("📝 Анализ текста", 0),
            ("🖼️ Анализ изображений", 1),
            ("🌐 Парсинг сайта", 2),
            ("📋 История", 3)
        ]
        
        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=index: self.switch_tab(idx))
            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)
        
        self.nav_buttons[0].setChecked(True)
        
        nav_layout.addStretch()
        
        # Status
        self.status_label = QLabel("● Проверка подключения...")
        self.status_label.setStyleSheet("color: #f59e0b; padding: 16px;")
        nav_layout.addWidget(self.status_label)
        
        layout.addWidget(nav_widget)
        parent_layout.addWidget(sidebar)
    
    def setup_content(self, parent_layout):
        """Создание области контента"""
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(40, 32, 40, 32)
        
        # Header
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 24)
        
        title = QLabel("Мониторинг конкурентов")
        title.setObjectName("title")
        
        subtitle = QLabel("AI-анализатор конкурентов: производство спортивной одежды")
        subtitle.setObjectName("subtitle")
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        content_layout.addWidget(header)
        
        # Stacked widget для вкладок
        self.stacked_widget = QStackedWidget()
        
        # Добавляем вкладки
        self.stacked_widget.addWidget(self.create_text_tab())
        self.stacked_widget.addWidget(self.create_image_tab())
        self.stacked_widget.addWidget(self.create_parse_tab())
        self.stacked_widget.addWidget(self.create_history_tab())
        
        content_layout.addWidget(self.stacked_widget)
        
        # Results area
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.hide()
        
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_scroll.setWidget(self.results_widget)
        
        content_layout.addWidget(self.results_scroll)
        
        # Loading indicator
        self.loading_widget = QWidget()
        loading_layout = QVBoxLayout(self.loading_widget)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setFixedWidth(300)
        
        self.loading_label = QLabel("Анализирую данные...")
        self.loading_label.setStyleSheet("color: #94a3b8; font-size: 16px;")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        loading_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.loading_label)
        
        self.loading_widget.hide()
        content_layout.addWidget(self.loading_widget)
        
        parent_layout.addWidget(content_widget)
    
    def create_text_tab(self) -> QWidget:
        """Вкладка анализа текста"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        
        title = QLabel("Анализ текста конкурента")
        title.setObjectName("cardTitle")
        
        desc = QLabel("Вставьте текст с сайта конкурента, из рекламы или описания продукта")
        desc.setObjectName("cardDescription")
        
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Вставьте текст конкурента для анализа...\n\nНапример: описание продукта, текст с лендинга, рекламное объявление...")
        self.text_input.setMinimumHeight(200)
        
        self.analyze_text_btn = QPushButton("⚡ Проанализировать")
        self.analyze_text_btn.setObjectName("primaryButton")
        self.analyze_text_btn.clicked.connect(self.analyze_text)
        
        card_layout.addWidget(title)
        card_layout.addWidget(desc)
        card_layout.addSpacing(16)
        card_layout.addWidget(self.text_input)
        card_layout.addSpacing(16)
        card_layout.addWidget(self.analyze_text_btn)
        
        layout.addWidget(card)
        layout.addStretch()
        
        return widget
    
    def create_image_tab(self) -> QWidget:
        """Вкладка анализа изображений"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        
        title = QLabel("Анализ изображений")
        title.setObjectName("cardTitle")
        
        desc = QLabel("Загрузите скриншот сайта, баннер или фото упаковки конкурента")
        desc.setObjectName("cardDescription")
        
        self.drop_zone = DropZone()
        
        self.analyze_image_btn = QPushButton("⚡ Проанализировать")
        self.analyze_image_btn.setObjectName("primaryButton")
        self.analyze_image_btn.clicked.connect(self.analyze_image)
        
        card_layout.addWidget(title)
        card_layout.addWidget(desc)
        card_layout.addSpacing(16)
        card_layout.addWidget(self.drop_zone)
        card_layout.addSpacing(16)
        card_layout.addWidget(self.analyze_image_btn)
        
        layout.addWidget(card)
        layout.addStretch()
        
        return widget
    
    def create_parse_tab(self) -> QWidget:
        """Вкладка парсинга сайта"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        
        title = QLabel("Парсинг сайта конкурента")
        title.setObjectName("cardTitle")
        
        desc = QLabel("Введите URL сайта для автоматического извлечения и анализа контента")
        desc.setObjectName("cardDescription")
        
        # URL input
        url_layout = QHBoxLayout()
        
        prefix = QLabel("https://")
        prefix.setStyleSheet("background-color: #243049; padding: 12px 16px; border-radius: 8px 0 0 8px; color: #64748b;")
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("example.com")
        self.url_input.setStyleSheet("border-radius: 0 8px 8px 0;")
        
        url_layout.addWidget(prefix)
        url_layout.addWidget(self.url_input)
        
        self.parse_btn = QPushButton("⚡ Парсить и анализировать")
        self.parse_btn.setObjectName("primaryButton")
        self.parse_btn.clicked.connect(self.parse_site)
        
        card_layout.addWidget(title)
        card_layout.addWidget(desc)
        card_layout.addSpacing(16)
        card_layout.addLayout(url_layout)
        card_layout.addSpacing(16)
        card_layout.addWidget(self.parse_btn)

        layout.addWidget(card)

        # Все конкуренты из config.py
        all_card = QFrame()
        all_card.setObjectName("card")
        all_layout = QVBoxLayout(all_card)
        all_layout.setContentsMargins(24, 24, 24, 24)

        all_title = QLabel("Все конкуренты из config.py")
        all_title.setObjectName("cardTitle")

        self.competitors_label = QLabel("Список загрузится с сервера")
        self.competitors_label.setObjectName("cardDescription")
        self.competitors_label.setWordWrap(True)

        self.parse_all_btn = QPushButton("⚡ Проанализировать всех конкурентов")
        self.parse_all_btn.setObjectName("primaryButton")
        self.parse_all_btn.clicked.connect(self.parse_all_competitors)

        all_layout.addWidget(all_title)
        all_layout.addWidget(self.competitors_label)
        all_layout.addSpacing(16)
        all_layout.addWidget(self.parse_all_btn)

        layout.addWidget(all_card)
        layout.addStretch()
        
        return widget
    
    def create_history_tab(self) -> QWidget:
        """Вкладка истории"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Header with clear button
        header = QHBoxLayout()
        
        title = QLabel("История запросов")
        title.setObjectName("cardTitle")
        
        self.clear_history_btn = QPushButton("🗑️ Очистить")
        self.clear_history_btn.setObjectName("secondaryButton")
        self.clear_history_btn.clicked.connect(self.clear_history)
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.clear_history_btn)
        
        layout.addLayout(header)
        
        # History scroll area
        self.history_scroll = QScrollArea()
        self.history_scroll.setWidgetResizable(True)
        
        self.history_widget = QWidget()
        self.history_layout = QVBoxLayout(self.history_widget)
        self.history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.history_scroll.setWidget(self.history_widget)
        layout.addWidget(self.history_scroll)
        
        return widget
    
    def switch_tab(self, index: int):
        """Переключение вкладок"""
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        
        self.stacked_widget.setCurrentIndex(index)
        self.results_scroll.hide()
        
        # Загружаем историю при переключении на вкладку
        if index == 3:
            self.load_history()
        if index == 2:
            self.load_competitors()
    
    def check_server_connection(self):
        """Проверка подключения к серверу"""
        if api_client.check_health():
            self.status_label.setText("● Система активна")
            self.status_label.setStyleSheet("color: #10b981; padding: 16px;")
        else:
            self.status_label.setText("● Сервер недоступен")
            self.status_label.setStyleSheet("color: #ef4444; padding: 16px;")
    
    def show_loading(self, message: str = "Анализирую данные..."):
        """Показать индикатор загрузки"""
        self.loading_label.setText(message)
        self.loading_widget.show()
        self.results_scroll.hide()
        
        # Отключаем кнопки
        self.analyze_text_btn.setEnabled(False)
        self.analyze_image_btn.setEnabled(False)
        self.parse_btn.setEnabled(False)
        self.parse_all_btn.setEnabled(False)
    
    def hide_loading(self):
        """Скрыть индикатор загрузки"""
        self.loading_widget.hide()
        
        # Включаем кнопки
        self.analyze_text_btn.setEnabled(True)
        self.analyze_image_btn.setEnabled(True)
        self.parse_btn.setEnabled(True)
        self.parse_all_btn.setEnabled(True)
    
    def clear_results(self, title_text: str = "📊 Результаты анализа"):
        """Очистить область результатов и поставить заголовок"""
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        title = QLabel(title_text)
        title.setObjectName("cardTitle")
        title.setStyleSheet("font-size: 18px; margin-bottom: 16px;")
        self.results_layout.addWidget(title)

    def show_results(self, analysis: dict, result_type: str = "text"):
        """Отображение результатов анализа"""
        self.clear_results()
        self.render_analysis(analysis, result_type)
        self.results_layout.addStretch()
        self.results_scroll.show()

    def add_niche_scores(self, analysis: dict):
        """Оценки design_score / animation_potential (поля под нишу)"""
        scores = QWidget()
        scores_layout = QHBoxLayout(scores)
        scores_layout.setContentsMargins(0, 0, 0, 0)
        scores_layout.addWidget(ScoreBlock("🎨 Дизайн (design_score)", analysis.get("design_score", 0)))
        scores_layout.addWidget(ScoreBlock("🎬 Потенциал анимации", analysis.get("animation_potential", 0)))
        self.results_layout.addWidget(scores)

    def render_analysis(self, analysis: dict, result_type: str = "text"):
        """Добавить виджеты анализа в область результатов"""
        if result_type == "text" or result_type == "parse":
            self.add_niche_scores(analysis)

            # Позиционирование бренда
            for key, label in [
                ("brand_positioning", "🏷️ Позиционирование"),
                ("target_audience", "👥 Целевая аудитория"),
                ("price_segment", "💰 Ценовой сегмент"),
            ]:
                if analysis.get(key):
                    self.results_layout.addWidget(TextBlock(label, analysis[key]))

            # Сильные стороны
            if analysis.get("strengths"):
                block = ResultBlock("✅ Сильные стороны", analysis["strengths"])
                self.results_layout.addWidget(block)
            
            # Слабые стороны
            if analysis.get("weaknesses"):
                block = ResultBlock("⚠️ Слабые стороны", analysis["weaknesses"])
                self.results_layout.addWidget(block)
            
            # Уникальные предложения
            if analysis.get("unique_offers"):
                block = ResultBlock("⭐ Уникальные предложения", analysis["unique_offers"])
                self.results_layout.addWidget(block)
            
            # Рекомендации
            if analysis.get("recommendations"):
                block = ResultBlock("💡 Рекомендации", analysis["recommendations"])
                self.results_layout.addWidget(block)
            
            # Резюме
            if analysis.get("summary"):
                summary_frame = QFrame()
                summary_frame.setObjectName("resultBlock")
                summary_frame.setStyleSheet("QFrame#resultBlock { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(6, 182, 212, 0.1), stop:1 rgba(139, 92, 246, 0.1)); }")
                summary_layout = QVBoxLayout(summary_frame)
                
                summary_title = QLabel("📝 Резюме")
                summary_title.setObjectName("sectionTitle")
                
                summary_text = QLabel(analysis["summary"])
                summary_text.setWordWrap(True)
                summary_text.setStyleSheet("color: #f1f5f9; font-size: 15px; line-height: 1.6;")
                
                summary_layout.addWidget(summary_title)
                summary_layout.addWidget(summary_text)
                self.results_layout.addWidget(summary_frame)
        
        elif result_type == "image":
            # Описание
            if analysis.get("description"):
                desc_frame = QFrame()
                desc_frame.setObjectName("resultBlock")
                desc_layout = QVBoxLayout(desc_frame)
                
                desc_title = QLabel("🖼️ Описание изображения")
                desc_title.setObjectName("sectionTitle")
                
                desc_text = QLabel(analysis["description"])
                desc_text.setWordWrap(True)
                desc_text.setStyleSheet("color: #94a3b8;")
                
                desc_layout.addWidget(desc_title)
                desc_layout.addWidget(desc_text)
                self.results_layout.addWidget(desc_frame)
            
            # Оценка стиля
            if "visual_style_score" in analysis:
                score = analysis["visual_style_score"]
                score_frame = QFrame()
                score_frame.setObjectName("resultBlock")
                score_layout = QVBoxLayout(score_frame)
                
                score_title = QLabel("⭐ Оценка визуального стиля")
                score_title.setObjectName("sectionTitle")
                
                score_value = QLabel(f"{score}/10")
                score_value.setStyleSheet("font-size: 32px; font-weight: bold; color: #22d3ee;")
                
                if analysis.get("visual_style_analysis"):
                    score_desc = QLabel(analysis["visual_style_analysis"])
                    score_desc.setWordWrap(True)
                    score_desc.setStyleSheet("color: #94a3b8;")
                    score_layout.addWidget(score_desc)
                
                score_layout.addWidget(score_title)
                score_layout.addWidget(score_value)
                self.results_layout.addWidget(score_frame)

            self.add_niche_scores(analysis)

            if analysis.get("product_presentation"):
                self.results_layout.addWidget(TextBlock("👕 Подача продукта", analysis["product_presentation"]))

            # Маркетинговые инсайты
            if analysis.get("marketing_insights"):
                block = ResultBlock("💡 Маркетинговые инсайты", analysis["marketing_insights"])
                self.results_layout.addWidget(block)

            # Идеи анимации
            if analysis.get("animation_ideas"):
                block = ResultBlock("🎬 Идеи анимации", analysis["animation_ideas"])
                self.results_layout.addWidget(block)

            # Рекомендации
            if analysis.get("recommendations"):
                block = ResultBlock("📋 Рекомендации", analysis["recommendations"])
                self.results_layout.addWidget(block)
    
    def show_error(self, message: str):
        """Показать сообщение об ошибке"""
        QMessageBox.critical(self, "Ошибка", message)
    
    # === API методы ===
    
    def analyze_text(self):
        """Анализ текста"""
        text = self.text_input.toPlainText().strip()
        
        if len(text) < 10:
            self.show_error("Введите текст минимум 10 символов")
            return
        
        self.show_loading("Анализирую текст...")
        
        self.current_worker = WorkerThread(api_client.analyze_text, text)
        self.current_worker.finished.connect(self.on_text_analysis_complete)
        self.current_worker.error.connect(lambda e: self.on_error(e))
        self.current_worker.start()
    
    def on_text_analysis_complete(self, result: dict):
        """Обработка результата анализа текста"""
        self.hide_loading()
        
        if result.get("success") and result.get("analysis"):
            self.show_results(result["analysis"], "text")
        else:
            self.show_error(result.get("error", "Неизвестная ошибка"))
    
    def analyze_image(self):
        """Анализ изображения"""
        if not self.drop_zone.selected_file:
            self.show_error("Выберите изображение для анализа")
            return
        
        self.show_loading("Анализирую изображение...")
        
        self.current_worker = WorkerThread(api_client.analyze_image, self.drop_zone.selected_file)
        self.current_worker.finished.connect(self.on_image_analysis_complete)
        self.current_worker.error.connect(lambda e: self.on_error(e))
        self.current_worker.start()
    
    def on_image_analysis_complete(self, result: dict):
        """Обработка результата анализа изображения"""
        self.hide_loading()
        
        if result.get("success") and result.get("analysis"):
            self.show_results(result["analysis"], "image")
        else:
            self.show_error(result.get("error", "Неизвестная ошибка"))
    
    def parse_site(self):
        """Парсинг сайта"""
        url = self.url_input.text().strip()
        
        if not url:
            self.show_error("Введите URL сайта")
            return
        
        self.show_loading("Загружаю и анализирую сайт...")
        
        self.current_worker = WorkerThread(api_client.parse_demo, url)
        self.current_worker.finished.connect(self.on_parse_complete)
        self.current_worker.error.connect(lambda e: self.on_error(e))
        self.current_worker.start()
    
    def on_parse_complete(self, result: dict):
        """Обработка результата парсинга"""
        self.hide_loading()
        
        if result.get("success") and result.get("data"):
            data = result["data"]
            if data.get("analysis"):
                self.show_results(data["analysis"], "parse")
            else:
                self.show_error("Не удалось проанализировать сайт")
        else:
            self.show_error(result.get("error", "Неизвестная ошибка"))

    def load_competitors(self):
        """Загрузить список конкурентов из config.py backend"""
        result = api_client.get_competitors()
        if result.get("urls"):
            self.competitors_label.setText(f"Ниша: {result.get('niche', '')}\n" + "\n".join(result["urls"]))

    def parse_all_competitors(self):
        """Парсинг и анализ всех конкурентов"""
        self.show_loading("Анализирую всех конкурентов... это займёт несколько минут")

        self.current_worker = WorkerThread(api_client.parse_competitors)
        self.current_worker.finished.connect(self.on_parse_all_complete)
        self.current_worker.error.connect(lambda e: self.on_error(e))
        self.current_worker.start()

    def on_parse_all_complete(self, result: dict):
        """Обработка результата парсинга всех конкурентов"""
        self.hide_loading()

        if not result.get("results"):
            self.show_error(result.get("error", "Не удалось проанализировать конкурентов"))
            return

        self.clear_results(f"📊 Конкуренты: {result['succeeded']} из {result['total']} проанализировано")

        for item in result["results"]:
            header = QLabel(f"🌐 {item['url']}")
            header.setStyleSheet("color: #22d3ee; font-size: 16px; font-weight: bold; margin-top: 16px;")
            self.results_layout.addWidget(header)

            analysis = (item.get("data") or {}).get("analysis")
            if item.get("success") and analysis:
                self.render_analysis(analysis, "parse")
            else:
                self.results_layout.addWidget(TextBlock("⚠️ Ошибка", item.get("error") or "Нет данных"))

        self.results_layout.addStretch()
        self.results_scroll.show()

    def load_history(self):
        """Загрузка истории"""
        result = api_client.get_history()
        
        # Очищаем
        while self.history_layout.count():
            child = self.history_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if result.get("items"):
            for item in result["items"]:
                frame = QFrame()
                frame.setObjectName("historyItem")
                layout = QHBoxLayout(frame)
                
                # Иконка
                icons = {"text": "📝", "image": "🖼️", "parse": "🌐"}
                icon = QLabel(icons.get(item.get("request_type", ""), "📄"))
                icon.setStyleSheet("font-size: 24px;")
                
                # Контент
                content = QWidget()
                content_layout = QVBoxLayout(content)
                content_layout.setContentsMargins(0, 0, 0, 0)
                
                type_labels = {"text": "Анализ текста", "image": "Анализ изображения", "parse": "Парсинг сайта"}
                type_label = QLabel(type_labels.get(item.get("request_type", ""), item.get("request_type", "")))
                type_label.setStyleSheet("color: #22d3ee; font-size: 12px; font-weight: bold;")
                
                summary = QLabel(item.get("request_summary", "")[:60] + "...")
                summary.setStyleSheet("color: #94a3b8;")
                
                content_layout.addWidget(type_label)
                content_layout.addWidget(summary)
                
                # Время
                timestamp = item.get("timestamp", "")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp)
                        time_str = dt.strftime("%d.%m %H:%M")
                    except:
                        time_str = timestamp[:16]
                else:
                    time_str = ""
                
                time_label = QLabel(time_str)
                time_label.setStyleSheet("color: #64748b; font-size: 12px;")
                
                layout.addWidget(icon)
                layout.addWidget(content, stretch=1)
                layout.addWidget(time_label)
                
                self.history_layout.addWidget(frame)
        else:
            empty_label = QLabel("📋 История пуста")
            empty_label.setStyleSheet("color: #64748b; font-size: 16px; padding: 40px;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.history_layout.addWidget(empty_label)
        
        self.history_layout.addStretch()
    
    def clear_history(self):
        """Очистка истории"""
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Вы уверены, что хотите очистить историю?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            api_client.clear_history()
            self.load_history()
    
    def on_error(self, error: str):
        """Обработка ошибки"""
        self.hide_loading()
        self.show_error(error)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

