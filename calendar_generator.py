from PIL import Image, ImageDraw, ImageFont
import calendar
import os
from datetime import datetime

class CalendarGenerator:
    THEMES = {
        "default": {
            "background": (25, 25, 35),
            "cell": (45, 45, 60),
            "busy": (220, 80, 60),
            "free": (80, 180, 120),
            "common_free": (65, 180, 130),
            "text": (240, 240, 240),
            "task_count": (255, 215, 0)
        },
        "blue": {
            "background": (20, 47, 72),   # #142f48
            "cell": (30, 140, 176),       # #1e8cb0
            "busy": (76, 68, 207),        # #4c44cf
            "free": (233, 83, 218),       # #e953da
            "common_free": (245, 193, 240), # #f5c1f0
            "text": (255, 255, 255),
            "task_count": (255, 255, 0)
        },
        "purple": {
            "background": (40, 0, 60),
            "cell": (80, 40, 100),
            "busy": (233, 83, 218),
            "free": (160, 100, 200),
            "common_free": (200, 150, 220),
            "text": (240, 240, 240),
            "task_count": (255, 215, 0)
        },
        "pink": {
            "background": (50, 0, 30),
            "cell": (120, 60, 100),
            "busy": (245, 193, 240),
            "free": (233, 83, 218),
            "common_free": (200, 100, 180),
            "text": (255, 255, 255),
            "task_count": (255, 200, 0)
        },
        "ocean": {
            "background": (10, 30, 50),
            "cell": (20, 80, 120),
            "busy": (30, 140, 176),
            "free": (100, 200, 220),
            "common_free": (150, 220, 240),
            "text": (220, 240, 255),
            "task_count": (255, 220, 50)
        }
    }

    def __init__(self):
        self.width = 800
        self.height = 600
        self.font_path = "arial.ttf" if os.name == 'nt' else "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
    
    def _get_font(self, size):
        try:
            return ImageFont.truetype(self.font_path, size)
        except IOError:
            return ImageFont.load_default()
    
    def generate_calendar(self, year, month, busy_days=None, free_days=None, common_free_days=None, theme='default'):
        theme_data = self.THEMES.get(theme, self.THEMES['default'])
        img = Image.new('RGB', (self.width, self.height), theme_data["background"])
        draw = ImageDraw.Draw(img)
        
        title_font = self._get_font(32)
        day_font = self._get_font(24)
        task_font = self._get_font(18)
        
        month_name = calendar.month_name[month]
        title = f"{month_name} {year}"
        title_width = draw.textlength(title, font=title_font)
        draw.text(((self.width - title_width) // 2, 20), title, font=title_font, fill=theme_data["text"])
        
        cal = calendar.monthcalendar(year, month)
        rows = len(cal)
        cols = 7
        
        cell_width = self.width // cols
        cell_height = (self.height - 100) // rows
        
        day_names = list(calendar.day_abbr)
        for i, name in enumerate(day_names):
            x = i * cell_width + cell_width // 2
            draw.text((x, 80), name, font=day_font, fill=theme_data["text"], anchor="mm")
        
        for week_idx, week in enumerate(cal):
            for day_idx, day in enumerate(week):
                if day == 0:
                    continue
                
                x = day_idx * cell_width + cell_width // 2
                y = week_idx * cell_height + 120
                
                cell_x1 = day_idx * cell_width + 5
                cell_y1 = week_idx * cell_height + 95
                cell_x2 = cell_x1 + cell_width - 10
                cell_y2 = cell_y1 + cell_height - 10
                
                if common_free_days and day in common_free_days:
                    color = theme_data["common_free"]
                elif free_days and day in free_days:
                    color = theme_data["free"]
                elif busy_days and day in busy_days:
                    color = theme_data["busy"]
                else:
                    color = theme_data["cell"]
                
                draw.rounded_rectangle(
                    [cell_x1, cell_y1, cell_x2, cell_y2],
                    radius=10,
                    fill=color
                )
                
                draw.text(
                    (x, y),
                    str(day),
                    font=day_font,
                    fill=theme_data["text"],
                    anchor="mm"
                )
                
                if busy_days and day in busy_days:
                    task_count = busy_days[day].get('task_count', 0)
                    if task_count > 0:
                        count_text = f"{task_count}"
                        count_width = draw.textlength(count_text, font=task_font)
                        draw.text(
                            (cell_x2 - count_width - 5, cell_y1 + 5),
                            count_text,
                            font=task_font,
                            fill=theme_data["task_count"]
                        )
        
        filename = f"calendar_{year}_{month}_{datetime.now().strftime('%H%M%S')}.png"
        img.save(filename)
        return filename

calendar_gen = CalendarGenerator()