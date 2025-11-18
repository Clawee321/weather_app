import tkinter as tk
from tkinter import messagebox
import requests
from io import BytesIO
from PIL import Image, ImageTk
import pandas as pd
import sys

API_KEY = "9f5d80b974ba325f52a205863ee448c6"
CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

forecast_icons_24h = []
forecast_icons_5d = []
forecast_data_global = None

# Ikony (trzymaj spacje jeśli chcesz, żeby tekst się nie przesuwał)
OPEN_ICON = "🔽   "   # gdy sekcja jest otwarta (z zachowanymi spacjami)
CLOSED_ICON = "▶️"    # gdy sekcja jest zamknięta

# --- wczytaj dane o miastach ---
cities_df = pd.read_csv("openweathermap_city_list.csv", usecols=["city_name","country"])
cities_df["city_name"] = cities_df["city_name"].astype(str)
cities_df["country"] = cities_df["country"].astype(str)

# ---------- Funkcje pomocnicze do przewijania ----------

def _bind_mousewheel(widget, canvas):
    """Binduje kółko myszy do przewijania `canvas` gdy kursor jest nad `widget`."""
    def _on_enter(event):
        widget.bind_all("<MouseWheel>", lambda e: _on_mousewheel(e, canvas))

    def _on_leave(event):
        widget.unbind_all("<MouseWheel>")

    widget.bind("<Enter>", _on_enter)
    widget.bind("<Leave>", _on_leave)


def _on_mousewheel(event, canvas):
    # Uniwersalna obsługa kółka myszy
    canvas.yview_scroll(-1 * int(event.delta / 120), "units")

def close_all_forecasts():
    """
    Jednoznacznie zamyka i czyści wszystkie sekcje prognoz
    oraz ustawia ikonki nagłówków na CLOSED_ICON.
    """
    global forecast_icons_24h, forecast_icons_5d
    pairs = (
        (forecast_24h_frame, forecast_icons_24h),
        (forecast_5d_frame, forecast_icons_5d),
    )
    for f, icons in pairs:
        try:
            # ustaw flagę jako 'zamknięta' i chowanie ramki
            f.forget_flag = True
            f.pack_forget()

            # niszczenie zawartości (canvas / widgety wewnątrz)
            for w in f.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass

            # czyść ikony
            icons.clear()

            # ustaw ikonę nagłówka na zamkniętą (jeśli header został przypisany)
            if hasattr(f, "header") and hasattr(f.header, "icon_label"):
                try:
                    f.header.icon_label.config(text=CLOSED_ICON)
                except Exception:
                    pass
        except Exception:
            # ignoruj błędy pojedynczego frame
            pass

    # natychmiast odśwież GUI
    try:
        root.update_idletasks()
    except Exception:
        pass

# ---------- Sugestie miast ----------

def update_suggestions(event):
    typed = city_entry.get().strip().lower()
    suggestion_box.delete(0, tk.END)
    if not typed:
        suggestion_box.place_forget()
        return

    matches = cities_df[cities_df["city_name"].str.lower().str.startswith(typed)]
    matches = matches.sort_values(by=["country"], key=lambda c: c != "PL")
    matches = matches.head(15)

    for _, row in matches.iterrows():
        display_name = f"{row['city_name']} ({row['country']})"
        suggestion_box.insert(tk.END, display_name)

    def place_suggestions():
        # suggestion_box jest umieszczony względem root — ale teraz search_frame
        # jest w inner_frame, tak więc liczymy pozycję względem root jak wcześniej
        x = search_frame.winfo_rootx() - root.winfo_rootx()
        y = search_frame.winfo_rooty() - root.winfo_rooty() + search_frame.winfo_height()
        suggestion_box.place(x=x, y=y)
        suggestion_box.lift()

    root.after(50, place_suggestions)


def fill_city(event):
    try:
        selected = suggestion_box.get(tk.ACTIVE)
    except Exception:
        selected = None
    if selected:
        city_entry.delete(0, tk.END)
        city_entry.insert(0, selected.split("(")[0].strip())
    suggestion_box.place_forget()


def hide_suggestions(event):
    if event.widget not in (city_entry, suggestion_box):
        suggestion_box.place_forget()

# ---------- Pobranie pogody ----------

def get_weather():
    global forecast_data_global
    city = city_entry.get().strip()
    if not city:
        messagebox.showwarning("Błąd", "Wpisz nazwę miasta!")
        return

    params = {"q": city, "appid": API_KEY, "units": "metric", "lang": "pl"}

    try:
        response = requests.get(CURRENT_URL, params=params, timeout=10)
        data = response.json()
        if data.get("cod") != 200:
            messagebox.showerror("Błąd", f"Nie znaleziono miasta: {city}")
            return

        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]
        desc = data["weather"][0]["description"].capitalize()
        icon_code = data["weather"][0]["icon"]

        city_label.config(text=city.upper())
        weather_label.config(
            text=f"{desc}\nTemperatura: {temp}°C (odczuwalna {feels_like}°C)\n"
                 f"Wilgotność: {humidity}%\nWiatr: {wind_speed} m/s"
        )

        icon_url = f"https://openweathermap.org/img/wn/{icon_code}@2x.png"
        icon_response = requests.get(icon_url, timeout=10)
        icon_img = Image.open(BytesIO(icon_response.content)).convert("RGBA")
        icon_img = icon_img.resize((175, 175), Image.LANCZOS)
        icon_photo = ImageTk.PhotoImage(icon_img)
        icon_label.config(image=icon_photo)
        icon_label.image = icon_photo

        forecast_response = requests.get(FORECAST_URL, params=params, timeout=10)
        forecast_data_global = forecast_response.json()

        # Po pobraniu nowych danych: zamknij i wyczyść poprzednie sekcje prognoz
        close_all_forecasts()

    except Exception as e:
        messagebox.showerror("Błąd", f"Wystąpił problem:\n{e}")

# ---------- Rozwijane prognozy (pełna szerokość) ----------

def toggle_forecast(frame, hours, header):
    global forecast_icons_24h, forecast_icons_5d
    if not forecast_data_global:
        messagebox.showwarning("Brak danych", "Najpierw pobierz pogodę!")
        return

    is_visible = frame.winfo_ismapped()
    if is_visible:
        frame.pack_forget()
        return

    for widget in frame.winfo_children():
        widget.destroy()

    if hours == 24:
        selected = forecast_data_global["list"][:8]
        icons_list = forecast_icons_24h
    else:
        selected = forecast_data_global["list"][::8]
        icons_list = forecast_icons_5d

    icons_list.clear()

    # Tworzymy canvas, który będzie poziomo przewijalny jeśli inner będzie szerszy niż canvas.
    canvas = tk.Canvas(frame, bg="lightblue", highlightthickness=0)
    h_scrollbar = tk.Scrollbar(frame, orient="horizontal", command=canvas.xview)
    canvas.configure(xscrollcommand=h_scrollbar.set)

    inner = tk.Frame(canvas, bg="lightblue")
    canvas.create_window((0, 0), window=inner, anchor="nw")

    # Nie wymuszamy szerokości okna wewnętrznego na szerokość canvas — dzięki temu
    # gdy kolumn jest dużo, inner stanie się szerszy i pojawi się poziomy scrollbar.
    canvas.pack(side="top", fill="both", expand=False) #true???
    h_scrollbar.pack(side="bottom", fill="x")

    # Dodawanie kolumn prognoz
    for i, forecast in enumerate(selected):
        if frame == forecast_24h_frame:
            time = forecast["dt_txt"].split()[1][:5]
        else:
            time = forecast["dt_txt"].split()[0]
        temp_f = forecast["main"]["temp"]
        desc_f = forecast["weather"][0]["description"].capitalize()
        icon_code_f = forecast["weather"][0]["icon"]

        icon_url_f = f"https://openweathermap.org/img/wn/{icon_code_f}@2x.png"
        icon_response_f = requests.get(icon_url_f, timeout=10)
        icon_img_f = Image.open(BytesIO(icon_response_f.content)).convert("RGBA")
        icon_photo_f = ImageTk.PhotoImage(icon_img_f)
        icons_list.append(icon_photo_f)

        col = tk.Frame(inner, bg="lightblue")
        # Ustawiamy grid tak aby kolumny były obok siebie i rozkładały się równomiernie
        col.grid(row=0, column=i, padx=5, pady=5, sticky="n")
        tk.Label(col, text=time, bg="lightblue", font=("Arial", 10, "bold")).pack()
        tk.Label(col, image=icon_photo_f, bg="lightblue").pack()
        tk.Label(col, text=f"{temp_f}°C", bg="lightblue", font=("Arial", 10)).pack()
        tk.Label(col, text=desc_f, bg="lightblue", font=("Arial", 8), wraplength=120, justify="center").pack()

    # Ustaw scrollregion po ułożeniu elementów
    inner.update_idletasks()
    canvas.config(scrollregion=canvas.bbox("all"))

    # Pokaż ramkę prognozy
    frame.pack(after=header, fill="x", pady=(0, 15))


def create_expandable_section(parent, title, hours, frame_forecast):
    header = tk.Frame(parent, bg="lightblue")
    header.pack(fill="x", pady=(5, 0))

    icon_label = tk.Label(header, text="▶️", bg="lightblue", fg="black", font=("Arial", 12, "bold"))
    icon_label.pack(side="left", padx=5)

    title_label = tk.Label(header, text=title, bg="lightblue", fg="black", font=("Arial", 12, "bold"))
    title_label.pack(side="left", padx=5, pady=5)

    frame_forecast.pack_forget()
    frame_forecast.forget_flag = True

    def toggle():
        if frame_forecast.forget_flag:
            frame_forecast.forget_flag = False
            icon_label.config(text=OPEN_ICON)
            toggle_forecast(frame_forecast, hours, header)
        else:
            frame_forecast.forget_flag = True
            icon_label.config(text=CLOSED_ICON)
            frame_forecast.pack_forget()

    header.bind("<Button-1>", lambda e: toggle())
    icon_label.bind("<Button-1>", lambda e: toggle())
    title_label.bind("<Button-1>", lambda e: toggle())

    frame_forecast.header = header
    header.icon_label = icon_label

    return frame_forecast

# ---------- GUI (z pionowym scrollbar) ----------
root = tk.Tk()
root.title("Aplikacja pogodowa")
root.geometry("720x850")
root.configure(bg="lightblue")

# Kontener z canvas + vertical scrollbar, aby cała aplikacja miała pionowy scrollbar
container = tk.Frame(root, bg="lightblue")
container.pack(fill="both", expand=True)

main_canvas = tk.Canvas(container, bg="lightblue", highlightthickness=0)
v_scrollbar = tk.Scrollbar(container, orient="vertical", command=main_canvas.yview)
main_canvas.configure(yscrollcommand=v_scrollbar.set)

v_scrollbar.pack(side="right", fill="y")
main_canvas.pack(side="left", fill="both", expand=True)

# inner_frame to miejsce, w którym dodajemy wszystkie widgety aplikacji
inner_frame = tk.Frame(main_canvas, bg="lightblue")
inner_id = main_canvas.create_window((0, 0), window=inner_frame, anchor="nw")

# Aktualizuj scrollregion gdy zawartość się zmienia
def _on_frame_config(e):
    main_canvas.configure(scrollregion=main_canvas.bbox("all"))

inner_frame.bind("<Configure>", _on_frame_config)

# Dopasuj szerokość inner_frame do szerokości canvas gdy canvas się zmienia
def _on_main_canvas_config(e):
    main_canvas.itemconfig(inner_id, width=e.width)

main_canvas.bind("<Configure>", _on_main_canvas_config)

# Bindowanie kółka myszy — gdy kursor nad canvas/inner_frame
_bind_mousewheel(main_canvas, main_canvas)

# --- Zawartość aplikacji (teraz w inner_frame zamiast root) ---

title_label = tk.Label(inner_frame, text="Sprawdź pogodę na świecie",
                       font=("Arial", 18, "bold"), bg="lightblue")
title_label.pack(pady=10)

# Wyszukiwanie
search_frame = tk.Frame(inner_frame, bg="lightblue")
search_frame.pack(pady=10)

city_entry = tk.Entry(search_frame, font=("Arial", 12), width=30,
                      relief="groove", borderwidth=3)
city_entry.grid(row=0, column=0, padx=(0, 5))

search_button = tk.Button(search_frame, text="Szukaj", command=get_weather,
                          bg="#0078D7", fg="white", font=("Arial", 10, "bold"),
                          relief="groove", borderwidth=3)
search_button.grid(row=0, column=1)

suggestion_box = tk.Listbox(root, height=6, width=40, font=("Arial", 11),
                            borderwidth=2, relief="groove")
suggestion_box.bind("<<ListboxSelect>>", fill_city)
city_entry.bind("<KeyRelease>", update_suggestions)
root.bind("<Button-1>", hide_suggestions)

icon_label = tk.Label(inner_frame, bg="lightblue")
icon_label.pack()

city_label = tk.Label(inner_frame, font=("Arial", 16, "bold"), bg="lightblue")
city_label.pack()

weather_label = tk.Label(inner_frame, font=("Arial", 13), bg="lightblue")
weather_label.pack(pady=(5, 20))

# --- Przyciski i ramki w kolejności ---
forecast_24h_frame = tk.Frame(inner_frame, bg="lightblue")
forecast_5d_frame = tk.Frame(inner_frame, bg="lightblue")

create_expandable_section(inner_frame, "Prognoza 24h", 24, forecast_24h_frame)
create_expandable_section(inner_frame, "Prognoza 5 dni", 120, forecast_5d_frame)

root.mainloop()
