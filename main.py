from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
                             QPushButton, QVBoxLayout, QFileDialog, QDialog, QStyleFactory,
                             QLineEdit, QLabel, QHBoxLayout, QGridLayout, QDateEdit, QMessageBox)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon, QPalette, QAction, QKeySequence, QShortcut
import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker
from functools import partial
import os
import datetime
import sys

Base = declarative_base()

# Определение структуры базы данных в основном окне
class ReportData(Base):
    __tablename__ = 'reports'
    id = Column(Integer, primary_key=True)
    date_modified = Column(String)
    file_name = Column(String)
    federal_district = Column(String)
    control_location = Column(String)
    control_period = Column(String)
    db_path = Column(String)

# Настройка подключения к базе данных и создание таблицы, если она не существует
engine = create_engine('sqlite:///reports.db')
Base.metadata.create_all(engine)

# Создание сессии для взаимодействия с базой данных
Session = sessionmaker(bind=engine)

class DataViewDialog(QDialog):
    # Конструктор класса для создания диалогового окна и редактирования данных
    def __init__(self, db_path, report_id, engine, parent=None):
        super().__init__(parent)
        self.db_path = db_path     # Путь к файлу базы данных
        self.report_id = report_id # Идентификатор отчета
        self.parent = parent       # Родительский виджет
        self.engine = engine       # Движок базы данных
        self.initUI()              # Инициализация интерфейса

    # Метод для инициализации пользовательского интерфейса диалога
    def initUI(self):
        self.setWindowTitle("Проверка и просмотр данных")
        self.setFixedSize(full_window_width, full_window_height) # Установка фиксированного размера окна

        layout = QGridLayout(self)

        # Создание и добавление меток и полей ввода
        labels = ["Федеральный округ (ФО)", "Место проведения контроля"]
        self.lineEdits = [QLineEdit(self) for _ in labels]

        fixed_width = 400 # Установка фиксированного размера для полей ввода
        for i, (label, lineEdit) in enumerate(zip(labels, self.lineEdits)):
            layout.addWidget(QLabel(label, self), i, 0)
            lineEdit = self.lineEdits[i]
            lineEdit.setFixedWidth(fixed_width)
            layout.addWidget(lineEdit, i, 1)

        # Поля ввода дат "С:" и "ПО:"
        layout.addWidget(QLabel("Период проведения контроля", self), 2, 0)
        self.dateStartEdit = QDateEdit()
        self.dateStartEdit.setCalendarPopup(True)
        self.dateStartEdit.setFixedWidth(fixed_width)
        layout.addWidget(QLabel("С:", self), 3, 0)
        layout.addWidget(self.dateStartEdit, 3, 1)

        self.dateEndEdit = QDateEdit()
        self.dateEndEdit.setCalendarPopup(True)
        self.dateEndEdit.setFixedWidth(fixed_width)
        layout.addWidget(QLabel("ПО:", self), 4, 0)
        layout.addWidget(self.dateEndEdit, 4, 1)

        # Создание кнопок "Сохранить" и "Отмена"
        self.saveButton = QPushButton("Сохранить", self)
        self.saveButton.clicked.connect(self.saveData)
        layout.addWidget(self.saveButton, 5, 0)

        self.cancelButton = QPushButton("Отмена", self)
        self.cancelButton.clicked.connect(self.close)
        layout.addWidget(self.cancelButton, 5, 1)

        # Создание таблицы для отображения данных из БД
        self.dbTable = QTableWidget(self)
        layout.addWidget(self.dbTable, 6, 0, 1, 4)
        self.load_data_from_db()
        self.load_report_data()

    # Метод для загрузки данных отчета из базы данных и их отображение в интерфейсе
    def load_report_data(self):
        report = self.parent.session.query(ReportData).filter(ReportData.id == self.report_id).first()
        if report:
            self.lineEdits[0].setText(report.federal_district or "")
            self.lineEdits[1].setText(report.control_location or "")
            period = report.control_period.split(" - ") if report.control_period else ["", ""]

            
            start_date = QDate.fromString(period[0], "dd.MM.yyyy")
            end_date = QDate.fromString(period[1], "dd.MM.yyyy")
            self.dateStartEdit.setDate(start_date)
            self.dateEndEdit.setDate(end_date )
        else:
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Error!")
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setText("Не удалось загрузить данные отчета!")
            dlg.exec()
            return

    # Метод для загрузки данных из базы данных в таблицу
    def load_data_from_db(self):
        engine = create_engine(f'sqlite:///{self.db_path}')
        self.df = pd.read_sql('new_table', con=engine) # Сохраняем DataFrame для использования при сохранении
        self.db_data = pd.read_sql('SELECT * FROM reports', con=self.engine)

        self.dbTable.setColumnCount(len(self.df.columns))
        self.dbTable.setHorizontalHeaderLabels(self.df.columns)
        self.dbTable.setRowCount(len(self.df.index))

        for i in range(len(self.df.index)):
            for j in range(len(self.df.columns)):
                value = self.df.iloc[i, j]
                if pd.isna(value):
                    continue # Пропускаем ячейки со значением NULL
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable) # Разрешение на редактирование
                self.dbTable.setItem(i, j, item)
        self.dbTable.resizeColumnsToContents()
        engine.dispose() # Закрытие соединения с базой данных

    @staticmethod
    def convert_to_db_format(date):
        return date.toString("dd.MM.yyyy")
    
    # Метод для сохранения данных из полей ввода в главное окно и базу данных
    def saveData(self):
        # Получаем запись по ID
        report = self.parent.session.query(ReportData).filter(ReportData.id == self.report_id).first()

        # Если запись не найдена, создаем новую
        if not report:
            report = ReportData(id=self.row)
            self.parent.session.add(report)

        # Обновляем данные
        report.date_modified = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        report.file_name = os.path.basename(self.db_path)
        report.federal_district = self.lineEdits[0].text()
        report.control_location = self.lineEdits[1].text()
        date_from = self.dateStartEdit.date()
        date_to = self.dateEndEdit.date()

        if date_from > date_to:
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Error")
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setText("Начальная дата больше чем конечная!")
            dlg.exec()
            return

        start_date = self.convert_to_db_format(date_from)
        end_date = self.convert_to_db_format(date_to)
        report.control_period = f"{start_date} - {end_date}"
        report.db_path = self.db_path

        # Сохраняем изменения в таблице
        updated_data = []
        for row in range(self.dbTable.rowCount()):
            row_data = []
            for col in range(self.dbTable.columnCount()):
                item = self.dbTable.item(row, col)
                row_data.append(item.text() if item else None)
            updated_data.append(row_data)

        # Запись обновленных данных в базу данных
        updated_df = pd.DataFrame(updated_data, columns=self.df.columns)
        local_engine = create_engine(f'sqlite:///{self.db_path}')
        updated_df.to_sql('new_table', con=local_engine, if_exists='replace', index=False)
        local_engine.dispose()

        # Сохраняем изменения в базе данных и обновляем данные в основном окне
        self.parent.session.commit()
        self.parent.load_data_from_db()
        self.accept()


    # Метод для установки введенных ранее данных в поля ввода
    def set_input_data(self, data):
        for i, lineEdit in enumerate(self.lineEdits):
            lineEdit.setText(data.get(f'lineEdit{i}', ''))
    
        start_date = QDate.fromString(data.get('dateStart', ''), "dd.MM.yyyy")
        end_date = QDate.fromString(data.get('dateEnd', ''), "dd.MM.yyyy")
        self.dateStartEdit.setDate(start_date)
        self.dateEndEdit.setDate(end_date)

    # Метод для получения введенных данных из полей ввода
    def get_input_data(self):
        data = {f'lineEdit{i}': lineEdit.text() for i, lineEdit in enumerate(self.lineEdits)}
        data['dateStart'] = self.dateStartEdit.text()
        data['dateEnd'] = self.dateEndEdit.text()
        return data


class ConfirmDeleteDialog(QDialog):
    # Конструктор класса для создания диалогового окна подтверждения удаления
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Подтверждение удаления")
        self.initUI() # Инициализация интерфейса пользователя
    
    # Метод для инициализации пользовательского интерфейса диалога
    def initUI(self):
        layout = QVBoxLayout(self)

        # Текст подтверждения
        label = QLabel("Вы действительно хотите удалить файл?")
        layout.addWidget(label)

        # Кнопки "Да" и "Нет"
        self.yesButton = QPushButton("Да", self)
        self.yesButton.clicked.connect(self.accept)
        self.noButton = QPushButton("Нет", self)
        self.noButton.clicked.connect(self.reject)

        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.yesButton)
        buttonLayout.addWidget(self.noButton)
        layout.addLayout(buttonLayout)

class MainWindow(QMainWindow):
    # Конструктор класса для создания главного окна приложения
    def __init__(self):
        super().__init__()
        
        # Устанавливает Fusion style
        QApplication.setStyle(QStyleFactory.create('Fusion'))
        self.dark_palette = QApplication.palette() 
        self.setPalette(self.dark_palette)

        # Определение пути к папке 'data' в директории исполняемого файла
        executable_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        self.data_folder = os.path.join(executable_dir, 'data')
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
        
        # Изменение пути создания основной базы данных
        self.engine = create_engine(f'sqlite:///{os.path.join(self.data_folder, "reports.db")}')
        Base.metadata.create_all(self.engine)
        
        self.session = Session(bind=self.engine)
        self.db_paths = {}       # Инициализация db_paths как пустого словаря путей к файлам
        self.input_data = {}     # Инициализация input_data как пустого словаря введенной информации
        self.initUI()            # Инициализация интерфейса пользователя
        self.load_data_from_db() # Загрузка данных из базы при инициализации
        self._instrument()       # Инициализация пунктов меню и их функций
        
    # Метод для инициализации пользовательского интерфейса главного окна
    def initUI(self):
        screen = app.primaryScreen()
        rect = screen.availableGeometry()
        width = rect.width()
        height = rect.height()
        keys = ['n', 'a', 'q']
	
        self.setWindowTitle("Загрузка и просмотр данных")
        # Установка значка окна
        icon_path = 'logo_xak.png'
        self.setWindowIcon(QIcon(icon_path))

        # Создание таблицы для отображения данных
        self.table = QTableWidget(self)
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["Дата изменения файла", "Имя файла БД", "Федеральный округ (ФО)", 
                                            "Место проведения контроля", "Период проведения контроля", 
                                            "Добавление отчета", "Просмотр отчета", "Удаление отчета"])
        self.table.verticalHeader().setVisible(False)
        self.table.setGeometry(10, round(height * 0.057), round(width * 0.7), round(height * 0.54))
        self.table.resizeColumnsToContents()
        
        # Масштабирование столбцов
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)

        # Создаем поисковую строку
        self.searchbar = QLineEdit(self)
        self.searchbar.setGeometry(10, round(height * 0.0332), round(width * 0.2), round(height * 0.02))
        self.searchbar.setText("Поиск")
        self.searchbar.focusInEvent = self.on_searchbar_focus_in #Очистка поисковой строки при нажатии на неё

        # Кнопка поиска
        self.search_button = QPushButton("🔍", self)
        self.search_button.setGeometry(round(width * 0.209), round(height * 0.0332), round(height * 0.02), round(height * 0.02))
        self.search_button.clicked.connect(self.on_search_button_clicked)

        # Кнопка отмены поиска
        self.search_cancel_button = QPushButton("❌", self)
        self.search_cancel_button.setGeometry(round(width * 0.22), round(height * 0.0332), round(height * 0.02), round(height * 0.02))

        # Подключение обработчика нажатия кнопки отмены поиска
        self.search_cancel_button.clicked.connect(self.on_search_cancel_button_clicked)

        # Кнопка для добавления отчета
        self.add_row_button = QPushButton("Добавить\nновый\nотчет", self)
        self.add_row_button.setGeometry(round(width * 0.7115), round(height * 0.057), round(height * 0.185), round(height * 0.1405))
        self.add_row_button.clicked.connect(self.add_row)

        #Горячая клавиша добавления отчёта
        shortcut_add_row_button = QShortcut(QKeySequence(f'Ctrl+{keys[0]}'), self)
        shortcut_add_row_button.activated.connect(self.add_row)

        #Кнопка "Справка"
        self.about = QPushButton("Справка", self)
        self.about.setGeometry(round(width * 0.7115), round(height * 0.257), round(height * 0.185), round(height * 0.1405))
        self.about.clicked.connect(self.show_about_dialog)

        #Горячая клавиша вызова справки
        shortcut_about = QShortcut(QKeySequence(f'Ctrl+{keys[1]}'), self)
        shortcut_about.activated.connect(self.show_about_dialog)

        #Кнопка "Выход"
        self.exit = QPushButton("Выход", self)
        self.exit.setGeometry(round(width * 0.7115), round(height * 0.457), round(height * 0.185), round(height * 0.1405))
        self.exit.clicked.connect(self.close)

        #Горячая клавиша выхода из программы
        shortcut_exit = QShortcut(QKeySequence(f'Ctrl+{keys[2]}'), self)
        shortcut_exit.activated.connect(self.close)

	# Справка о программе
    def show_about_dialog(self):
        about_text = "Главное окно:\n\t•Добавить новый отчет - добавление ячейки таблицы \n\t•Добавить - добавление исходного (.xls .xlsx) файла в таблицу и в базу данных\n\t"\
            "•Просмотреть - открыть окно для просмотра и редактирования файла (.db)\n\t•❌- удалить файл (.db)\n\t•Поиск - выдает все совпадения по вашему запросу \n\t•Инструменты:\n\t\t-Сортировать по возрастанию\n\t\t\t"\
                "-По федеральному округу\n\t\t\t-По месту проведения контроля\n\t\t\t-По дате изменения\n\t\t-Сортировать по Убыванию\n\t\t\t-По федеральному округу\n\t\t\t"\
                    "-По месту проведения контроля\n\t\t\t-По дате изменения\nДиалоговое окно (Проверка и просмотр данных):\n\t•Введение данных о загруженном файле (задается пользователем)\n\t\t-Федеральный округ (ФО)\n\t\t-Место проведения контроля"\
                        "\n\t\t-Период проведения контроля\n\t•Сохранить - сохраняет изменения в базу данных\n\t•Отмена - выход из диалогового окна без сохранения изменений"\
	                    "\nГорячие клавиши по умолчанию:"\
                                "\n\t•Добавить новый отчет - Ctrl + n"\
                                "\n\t•Вызвать справку - Ctrl + a"\
                                "\n\t•Закрыть программу - Ctrl + q"\
                            "\n\nДанное ПО разработано в рамках хакатона \"Всероссийский Хакатон Связи 2023\" командой \"Добровольцы\" 💪"
        dlg = QDialog(self)
        layout = QVBoxLayout()
        label = QLabel(about_text, dlg)
        layout.addWidget(label)
        dlg.setLayout(layout)
        dlg.setWindowTitle("Справка")
        dlg.exec()
        
    # Метод для очистка поля поиска при нажатии на него
    def on_searchbar_focus_in(self, event):
        if self.searchbar.text() == "Поиск":
            self.searchbar.clear()

    # Метод для обработки нажатия на кнопку поиска
    def on_search_button_clicked(self):
        # Получаем текущий текст в поисковой строке
        search_term = self.searchbar.text().lower()
        self.search_in_table(search_term)
        
    # Метод поиска по таблице на основе введенного запроса
    def search_in_table(self, search_term):
        for row in range(self.table.rowCount()):
            row_visible = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and search_term in item.text().lower():
                    row_visible = True
                    break
            self.table.setRowHidden(row, not row_visible)
            
    # Метод для отмены фильтрации поиска и отображение всех строк
    def on_search_cancel_button_clicked(self):
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, False)

    # Метод для загрузки данных из базы данных и их отображение в таблице главного окна
    def load_data_from_db(self):
        # Очищаем текущие данные в таблице
        self.table.setRowCount(0)

        # Загружаем данные из базы данных
        for report in self.session.query(ReportData).all():
            # Создаем новую строку в таблице для каждого отчета
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)
            
            # Создаем и добавляем QTableWidgetItem с флагом ItemIsEnabled
            items = [
                QTableWidgetItem(report.date_modified),
                QTableWidgetItem(report.file_name),
                QTableWidgetItem(report.federal_district),
                QTableWidgetItem(report.control_location),
                QTableWidgetItem(report.control_period)
            ]

            for i, item in enumerate(items):
                item.setFlags(Qt.ItemFlag.ItemIsEnabled) # Флаг делает элементы неизменяемыми
                self.table.setItem(row_position, i, item)

            # Добавляем кнопки управления для каждой строки
            add_button = QPushButton("Добавить", self.table)
            add_button.clicked.connect(lambda _, row=row_position: self.openFileDialog(row))
            self.table.setCellWidget(row_position, 5, add_button)

            view_button = QPushButton("Просмотреть", self.table)
            # Передача id отчета вместо позиции строки
            view_button.clicked.connect(lambda _, report_id=report.id: self.viewDialog(report_id))
            self.table.setCellWidget(row_position, 6, view_button)

            delete_button = QPushButton("❌", self.table)
            delete_button.clicked.connect(partial(self.confirmDelete, delete_button))
            self.table.setCellWidget(row_position, 7, delete_button)

            # Обновляем словарь db_paths для текущего отчета
            self.db_paths[report.id] = {
                "view_button": view_button,
                "db_path": report.db_path,
                "report_id": report.id
            }
            self.print_db_contents()

    # Метод для вывода содержимого базы данных в консоль для отладки
    def print_db_contents(self):
        print("Содержимое базы данных:")
        for report in self.session.query(ReportData).all():
            print(f"ID: {report.id}, Date Modified: {report.date_modified}, File Name: {report.file_name}, "
                  f"Federal District: {report.federal_district}, Control Location: {report.control_location}, "
                  f"Control Period: {report.control_period}, DB Path: {report.db_path}")
        print("")

    # Метод для добавления новой строки в таблицу
    def add_row(self):
        # Получение текущего количества строк и добавление новой строки
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)

        # Инициализация db_paths для новой строки
        self.db_paths[row_position] = {"view_button": None, "db_path": None}

        # Для каждой ячейки создаем виджет QLabel (или другой виджет по выбору)
        for i in range(self.table.columnCount() - 3):  # Исключая столбцы для кнопок
            self.table.setCellWidget(row_position, i, QLabel(""))

        # Кнопка "Добавить"
        add_button = QPushButton("Добавить", self.table)
        # Изменение лямбда-функции для передачи текущей строки
        add_button.clicked.connect(lambda _, row=row_position: self.openFileDialog(row))
        self.table.setCellWidget(row_position, 5, add_button)

        # Создание кнопки "Просмотреть" и сохранение ссылки на неё в db_paths
        view_button = QPushButton("Просмотреть", self.table)
        view_button.setEnabled(False)
        view_button.clicked.connect(lambda _, row=row_position: self.viewDialog(row))
        self.table.setCellWidget(row_position, 6, view_button)
        self.db_paths[row_position]["view_button"] = view_button

        # Создание кнопки "Удалить"
        delete_button = QPushButton("❌", self.table)
        delete_button.clicked.connect(lambda: self.confirmDelete(delete_button))
        self.table.setCellWidget(row_position, 7, delete_button)

    # Метод для подтверждения удаления строки из таблицы
    def confirmDelete(self, button):
        row = self.table.indexAt(button.pos()).row()
        if row >= 0:
            confirm_dialog = ConfirmDeleteDialog(self)
            if confirm_dialog.exec() == QDialog.DialogCode.Accepted:
                report_id = self.get_report_id(row)
                if report_id:
                    self.delete_report_from_db(report_id)
                self.table.removeRow(row)  # Удаляем строку из таблицы независимо от наличия в базе данных
                self.update_ui_after_deletion(row)

    # Метод доя получения идентификатора отчета на основе строки таблицы
    def get_report_id(self, row):
        # Получение даты и времени изменения файла из первой ячейки строки
        date_modified_item = self.table.item(row, 0)
        date_modified = date_modified_item.text() if date_modified_item else None

        if date_modified:
            # Поиск записи в базе данных по дате и времени изменения
            report = self.session.query(ReportData).filter_by(date_modified=date_modified).first()
            if report:
                return report.id

        return None

    # Метод для удаления отчета из базы данных
    def delete_report_from_db(self, report_id):
        report = self.session.get(ReportData, report_id)
        if report:
            db_file_path = report.db_path
            self.session.delete(report)
            self.session.commit()

            if db_file_path and os.path.exists(db_file_path):
                try:
                    os.remove(db_file_path)
                    print(f"Файл {db_file_path} успешно удален")
                except OSError as e:
                    print(f"Ошибка при удалении файла {db_file_path}: {e.strerror}. Файл не удален.")
                    self.session.add(report)
                    self.session.commit()

    # Метод для обновления пользовательского интерфейса после удаления строки
    def update_ui_after_deletion(self, deleted_row):
        if deleted_row in self.db_paths:
            del self.db_paths[deleted_row]
        if deleted_row in self.input_data:
            del self.input_data[deleted_row]

        # Обновление индексов в db_paths и input_data
        new_db_paths = {}
        new_input_data = {}
        for row_index in range(self.table.rowCount()):
            if row_index in self.db_paths:
                new_db_paths[row_index] = self.db_paths[row_index]
            if row_index in self.input_data:
                new_input_data[row_index] = self.input_data[row_index]

        self.db_paths = new_db_paths
        self.input_data = new_input_data

    # Метод для открытия диалога выбора файла и загрузки данных в БД
    def openFileDialog(self, row):
        current_datetime = datetime.datetime.now()
        current_datetime = current_datetime.replace(microsecond=0)
        datetime_for_name = current_datetime.strftime("%d%m%Y_%H%M%S")
        datetime_for_db = current_datetime.strftime("%d.%m.%Y %H:%M:%S")
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите файл Excel", "", "Excel Files (*.xlsx *.xls)")
        if file_path:
            db_path = self.excel_to_db(file_path, datetime_for_name)
            db_file_name = os.path.basename(db_path)  # Получаем имя файла базы данных
            print(f"Данные сохранены в {db_path}")

            # Создаем новую запись в базе данных
            report = ReportData(date_modified=datetime_for_db, file_name=db_file_name, db_path=db_path)
            self.session.add(report)
            self.session.commit()

            # Обновляем таблицу и db_paths
            self.load_data_from_db()
            self.db_paths[report.id] = {
                "view_button": self.table.cellWidget(row, 6),
                "db_path": db_path
            }

    # Метод для открытия диалогового окна для просмотра и редактирования данных отчета
    def viewDialog(self, report_id):
        # Получаем путь к файлу базы данных и другие данные по ID отчета
        report = self.session.query(ReportData).filter(ReportData.id == report_id).first()
        if report and report.db_path:
            dialog = DataViewDialog(report.db_path, report_id, self.engine, self)
            if report_id in self.input_data:
                dialog.set_input_data(self.input_data[report_id])
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.input_data[report_id] = dialog.get_input_data()
        else:
            print("Файл не загружен.")

    # Метод для чтения данных из excel файла и записи их в базу данных
    def excel_to_db(self, excel_path, timestamp):
        # Чтение данных из excel файла
        df = pd.read_excel(excel_path, header=16)

        # Создание уникального имени файла для новой БД
        db_name = f"database_{timestamp}.db"
        db_path = os.path.join(self.data_folder, db_name)

        # Запись данных в новую БД
        local_engine = create_engine(f'sqlite:///{db_path}')
        df.to_sql('new_table', con=local_engine, if_exists='replace', index=False)
        local_engine.dispose()  # Явное закрытие соединения с БД
        return db_path

    # Метод для настройки пунктов меню и их функций
    def _instrument(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("Инструменты")

        # Создаем действия для сортировки
        sort_asc_fd_action = QAction("По федеральному округу", self)
        sort_asc_cl_action = QAction("По месту проведения контроля", self)
        sort_asc_date_action = QAction("По дате изменения", self)

        sort_desc_fd_action = QAction("По федеральному округу", self)
        sort_desc_cl_action = QAction("По месту проведения контроля", self)
        sort_desc_date_action = QAction("По дате изменения", self)

        reset_sort_action = QAction("Сбросить сортировку", self)

        # Подключаем сигналы к слотам
        sort_asc_fd_action.triggered.connect(lambda: self.sort_data(2, Qt.SortOrder.AscendingOrder))
        sort_asc_cl_action.triggered.connect(lambda: self.sort_data(3, Qt.SortOrder.AscendingOrder))
        sort_asc_date_action.triggered.connect(lambda: self.sort_data(0, Qt.SortOrder.AscendingOrder))

        sort_desc_fd_action.triggered.connect(lambda: self.sort_data(2, Qt.SortOrder.DescendingOrder))
        sort_desc_cl_action.triggered.connect(lambda: self.sort_data(3, Qt.SortOrder.DescendingOrder))
        sort_desc_date_action.triggered.connect(lambda: self.sort_data(0, Qt.SortOrder.DescendingOrder))

        reset_sort_action.triggered.connect(self.reset_sort)

        file_submenu_1 = file_menu.addMenu("Сортировать по возрастанию")
        file_submenu_2 = file_menu.addMenu("Сортировать по убыванию")

        file_submenu_1.addAction(sort_asc_fd_action)
        file_submenu_1.addAction(sort_asc_cl_action)
        file_submenu_1.addAction(sort_asc_date_action)

        file_submenu_2.addAction(sort_desc_fd_action)
        file_submenu_2.addAction(sort_desc_cl_action)
        file_submenu_2.addAction(sort_desc_date_action)

        file_menu.addAction(reset_sort_action)

    # Метод для сортировки данных в таблице
    def sort_data(self, column, order):
        self.table.sortItems(column, order)

    # Метод для сброса сортировки данных в таблице
    def reset_sort(self):
        self.table.sortItems(0, Qt.SortOrder.AscendingOrder)

# Запуск приложения
app = QApplication(sys.argv)
main_window = MainWindow()

# Установка корректного размера окна
screen_size = app.primaryScreen().size()
full_window_width = int(screen_size.width() * 0.9)
full_window_height = int(screen_size.height() * 0.8)
window_width = int(screen_size.width() * 0.82)
window_height = int(screen_size.height() * 0.6)
main_window.setMaximumSize(window_width, window_height)
main_window.setMinimumSize(window_width, window_height)
main_window.show()

# Выход из приложения
sys.exit(app.exec())
