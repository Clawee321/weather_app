import tkinter as tk
from tkinter import messagebox
import requests
from io import BytesIO
from PIL import Image, ImageTk
import pandas as pd
import sys
import threading

API_KEY = "c6b8d4c1c00f01641121854c740183dd"
CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

BG_PRIMARY = "#cfe8f8"
BG_CARD = "#95cbf0"
ACCENT = "#0c7fb5"
TEXT_PRIMARY = "#08243b"
TEXT_MUTED = "#1c4763"
INPUT_BG = "#b7dcf4"
INPUT_BORDER = "#8bbad6"

forecast_icons_24h = []
forecast_icons_5d = []
forecast_data_global = None
loading_animation_id = None
forecast_loading_ids = {}

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
        selection = event.widget.curselection()
        if selection:
            selected = event.widget.get(selection[0])
        else:
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

def _start_loading_animation(label, base_text, animation_key):
    def animate(step=0):
        dots = "." * (step % 4)
        label.config(text=f"{base_text}{dots}")
        animation_id = root.after(400, animate, step + 1)
        forecast_loading_ids[animation_key] = animation_id

    animate()


def _stop_loading_animation(animation_key):
    animation_id = forecast_loading_ids.pop(animation_key, None)
    if animation_id:
        root.after_cancel(animation_id)


def set_loading(is_loading):
    global loading_animation_id
    if is_loading:
        loading_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        loading_overlay.lift()
        search_button.config(state="disabled")
        city_entry.config(state="disabled")
        suggestion_box.place_forget()
        if loading_animation_id is None:
            def animate(step=0):
                global loading_animation_id
                dots = "." * (step % 4)
                loading_label.config(text=f"Ładowanie danych pogody{dots}")
                loading_animation_id = root.after(400, animate, step + 1)

            animate()
    else:
        if loading_animation_id is not None:
            root.after_cancel(loading_animation_id)
            loading_animation_id = None
        loading_overlay.place_forget()
        search_button.config(state="normal")
        city_entry.config(state="normal")


def _finish_error(message, title="Błąd", kind="error"):
    set_loading(False)
    if kind == "warning":
        messagebox.showwarning(title, message)
    else:
        messagebox.showerror(title, message)


def _finish_success(city, data, icon_img, forecast_data):
    global forecast_data_global

    temp = data["main"]["temp"]
    feels_like = data["main"]["feels_like"]
    humidity = data["main"]["humidity"]
    wind_speed = data["wind"]["speed"]
    desc = data["weather"][0]["description"].capitalize()

    city_label.config(text=city.upper())
    weather_label.config(
        text=f"{desc}\nTemperatura: {temp}°C (odczuwalna {feels_like}°C)\n"
             f"Wilgotność: {humidity}%\nWiatr: {wind_speed} m/s"
    )

    icon_photo = ImageTk.PhotoImage(icon_img)
    icon_label.config(image=icon_photo)
    icon_label.image = icon_photo

    forecast_data_global = forecast_data

    # Po pobraniu nowych danych: zamknij i wyczyść poprzednie sekcje prognoz
    close_all_forecasts()
    set_loading(False)


def get_weather():
    city = city_entry.get().strip()
    if not city:
        messagebox.showwarning("Błąd", "Wpisz nazwę miasta!")
        return
    set_loading(True)
    def fetch_weather():
        params = {"q": city, "appid": API_KEY, "units": "metric", "lang": "pl"}
        try:
            response = requests.get(CURRENT_URL, params=params, timeout=10)
            data = response.json()
            if data.get("cod") != 200:
                root.after(0, _finish_error, f"Nie znaleziono miasta: {city}")
                return

            icon_code = data["weather"][0]["icon"]
            icon_url = f"https://openweathermap.org/img/wn/{icon_code}@2x.png"
            icon_response = requests.get(icon_url, timeout=10)
            icon_img = Image.open(BytesIO(icon_response.content)).convert("RGBA")
            icon_img = icon_img.resize((175, 175), Image.LANCZOS)

            forecast_response = requests.get(FORECAST_URL, params=params, timeout=10)
            forecast_data = forecast_response.json()

            root.after(0, _finish_success, city, data, icon_img, forecast_data)
        except Exception as e:
            root.after(0, _finish_error, f"Wystąpił problem:\n{e}")

    threading.Thread(target=fetch_weather, daemon=True).start()

# ---------- Rozwijane prognozy (pełna szerokość) ----------

def _render_forecast(frame, selected):
    for widget in frame.winfo_children():
        widget.destroy()

    canvas = tk.Canvas(frame, bg=BG_CARD, highlightthickness=0, borderwidth=0)
    h_scrollbar = tk.Scrollbar(frame, orient="horizontal", command=canvas.xview, troughcolor=BG_CARD)
    canvas.configure(xscrollcommand=h_scrollbar.set)

    inner = tk.Frame(canvas, bg=BG_CARD)
    canvas.create_window((0, 0), window=inner, anchor="nw")

    canvas.pack(side="top", fill="both", expand=False)
    h_scrollbar.pack(side="bottom", fill="x")

    for i, forecast in enumerate(selected):
        if frame == forecast_24h_frame:
            time = forecast["time"]
        else:
            time = forecast["time"]
        temp_f = forecast["temp"]
        desc_f = forecast["desc"]
        icon_photo_f = forecast["icon"]

        col = tk.Frame(inner, bg=BG_CARD)
        col.grid(row=0, column=i, padx=5, pady=5, sticky="n")
        tk.Label(col, text=time, bg=BG_CARD, fg=TEXT_PRIMARY, font=("Segoe UI", 10, "bold")).pack()
        tk.Label(col, image=icon_photo_f, bg=BG_CARD).pack()
        tk.Label(col, text=f"{temp_f}°C", bg=BG_CARD, fg=TEXT_PRIMARY, font=("Segoe UI", 10)).pack()
        tk.Label(
            col,
            text=desc_f,
            bg=BG_CARD,
            fg=TEXT_MUTED,
            font=("Segoe UI", 9),
            wraplength=140,
            justify="center",
        ).pack()

    inner.update_idletasks()
    canvas.config(scrollregion=canvas.bbox("all"))


def _finish_forecast(frame, header, selected, animation_key):
    _stop_loading_animation(animation_key)
    _render_forecast(frame, selected)
    frame.pack(after=header, fill="x", pady=(0, 15))


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
        animation_key = "forecast_24h"
    else:
        selected = forecast_data_global["list"][::8]
        icons_list = forecast_icons_5d
        animation_key = "forecast_5d"

    icons_list.clear()

    loading_label = tk.Label(
        frame,
        text="Ładowanie prognozy",
        bg=BG_CARD,
        fg=TEXT_PRIMARY,
        font=("Segoe UI", 11, "bold"),
    )
    loading_label.pack(pady=12)
    frame.pack(after=header, fill="x", pady=(0, 15))
    _start_loading_animation(loading_label, "Ładowanie prognozy", animation_key)

    def fetch_forecast():
        forecasts = []
        try:
            for forecast in selected:
                if frame == forecast_24h_frame:
                    time = forecast["dt_txt"].split()[1][:5]
                else:
                    time = forecast["dt_txt"].split()[0]
                temp_f = forecast["main"]["temp"]
                desc_f = forecast["weather"][0]["description"].capitalize()
                icon_code_f = forecast["weather"][0]["icon"]

                icon_url_f = f"https://openweathermap.org/img/wn/{icon_code_f}@2x.png"
                icon_response_f = requests.get(icon_url_f, timeout=10)
                icon_bytes = icon_response_f.content
                forecasts.append((time, temp_f, desc_f, icon_bytes))
        except Exception:
            forecasts = []

        def render():
            if not frame.winfo_exists():
                return
            if not forecasts:
                _stop_loading_animation(animation_key)
                loading_label.config(text="Nie udało się wczytać prognozy.")
                return

            prepared = []
            for time, temp_f, desc_f, icon_bytes in forecasts:
                icon_img_f = Image.open(BytesIO(icon_bytes)).convert("RGBA")
                icon_photo_f = ImageTk.PhotoImage(icon_img_f)
                icons_list.append(icon_photo_f)
                prepared.append(
                    {
                        "time": time,
                        "temp": temp_f,
                        "desc": desc_f,
                        "icon": icon_photo_f,
                    }
                )

            _finish_forecast(frame, header, prepared, animation_key) 

        root.after(0, render)

    threading.Thread(target=fetch_forecast, daemon=True).start()


def create_expandable_section(parent, title, hours, frame_forecast):
    header = tk.Frame(parent, bg=BG_CARD)
    header.pack(fill="x", pady=(5, 0))

    icon_label = tk.Label(header, text="▶️", bg=BG_CARD, fg=TEXT_PRIMARY, font=("Segoe UI", 12, "bold"))
    icon_label.pack(side="left", padx=5)

    title_label = tk.Label(header, text=title, bg=BG_CARD, fg=TEXT_PRIMARY, font=("Segoe UI", 12, "bold"))
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
root.geometry("760x600")
root.configure(bg=BG_PRIMARY)

# Nakładka ładowania
loading_overlay = tk.Frame(root, bg=BG_PRIMARY)
loading_label = tk.Label(
    loading_overlay,
    text="Ładowanie danych pogody...",
    font=("Segoe UI", 16, "bold"),
    bg=BG_PRIMARY,
    fg=TEXT_PRIMARY,
)
loading_label.place(relx=0.5, rely=0.5, anchor="center")


# Kontener z canvas + vertical scrollbar, aby cała aplikacja miała pionowy scrollbar
container = tk.Frame(root, bg=BG_PRIMARY)
container.pack(fill="both", expand=True, padx=16, pady=16)

main_canvas = tk.Canvas(container, bg=BG_PRIMARY, highlightthickness=0, borderwidth=0)
v_scrollbar = tk.Scrollbar(container, orient="vertical", command=main_canvas.yview, troughcolor=BG_PRIMARY)
main_canvas.configure(yscrollcommand=v_scrollbar.set)

v_scrollbar.pack(side="right", fill="y")
main_canvas.pack(side="left", fill="both", expand=True)

# inner_frame to miejsce, w którym dodajemy wszystkie widgety aplikacji
inner_frame = tk.Frame(main_canvas, bg=BG_PRIMARY)
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

card_frame = tk.Frame(
    inner_frame,
    bg=BG_CARD,
    padx=18,
    pady=18,
    highlightthickness=1,
    highlightbackground=ACCENT,
    bd=0,
)
card_frame.pack(fill="both", expand=True, padx=12, pady=12)

title_label = tk.Label(
    card_frame,
    text="Sprawdź pogodę na świecie",
    font=("Segoe UI", 20, "bold"),
    bg=BG_CARD,
    fg=TEXT_PRIMARY,
)
title_label.pack(pady=(0, 14))

subtitle = tk.Label(
    card_frame,
    text="Wpisz nazwę miasta i poznaj aktualną pogodę oraz prognozy",
    font=("Segoe UI", 11),
    bg=BG_CARD,
    fg=TEXT_MUTED,
)
subtitle.pack()

# Dekoracyjny separator
tk.Frame(card_frame, bg=ACCENT, height=2).pack(fill="x", pady=(12, 16))

# Wyszukiwanie
search_frame = tk.Frame(card_frame, bg=BG_CARD)
search_frame.pack(pady=10)

city_entry = tk.Entry(
    search_frame,
    font=("Segoe UI", 12),
    width=30,
    relief="flat",
    borderwidth=0,
    highlightthickness=1,
    highlightbackground=INPUT_BORDER,
    highlightcolor=INPUT_BORDER,
    bg=INPUT_BG,
    fg=TEXT_PRIMARY,
    insertbackground=TEXT_PRIMARY,
)
city_entry.grid(row=0, column=0, padx=(0, 8), ipady=6)

search_button = tk.Button(
    search_frame,
    text="Szukaj",
    command=get_weather,
    bg=ACCENT,
    fg=BG_PRIMARY,
    font=("Segoe UI", 11, "bold"),
    relief="flat",
    borderwidth=0,
    padx=16,
    pady=6,
    activebackground="#0ea5e9",
    activeforeground=BG_PRIMARY,
    cursor="hand2",
)
search_button.grid(row=0, column=1)

suggestion_box = tk.Listbox(
    root,
    height=6,
    width=40,
    font=("Segoe UI", 11),
    borderwidth=0,
    relief="flat",
    bg=INPUT_BG,
    fg=TEXT_PRIMARY,
    highlightthickness=1,
    highlightbackground=ACCENT,
    selectbackground=ACCENT,
    selectforeground=BG_PRIMARY,
)
suggestion_box.bind("<<ListboxSelect>>", fill_city)
city_entry.bind("<KeyRelease>", update_suggestions)
root.bind("<Button-1>", hide_suggestions)

icon_label = tk.Label(card_frame, bg=BG_CARD)
icon_label.pack(pady=(8, 0))

city_label = tk.Label(
    card_frame,
    font=("Segoe UI", 18, "bold"),
    bg=BG_CARD,
    fg=TEXT_PRIMARY,
)
city_label.pack()

weather_label = tk.Label(
    card_frame,
    font=("Segoe UI", 12),
    bg=BG_CARD,
    fg=TEXT_PRIMARY,
    justify="center",
)
weather_label.pack(pady=(5, 20))

# --- Przyciski i ramki w kolejności ---
forecast_24h_frame = tk.Frame(card_frame, bg=BG_CARD)
forecast_5d_frame = tk.Frame(card_frame, bg=BG_CARD)

create_expandable_section(card_frame, "Prognoza 24h", 24, forecast_24h_frame)
create_expandable_section(card_frame, "Prognoza 5 dni", 120, forecast_5d_frame)

root.mainloop()
