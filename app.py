import tkinter as tk
from tkinter import messagebox
import requests
from io import BytesIO
from PIL import Image, ImageTk

# 🔑 Twój klucz API
API_KEY = "9f5d80b974ba325f52a205863ee448c6"

# URL do aktualnej pogody i prognozy
CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

# Lista do przechowywania ikon prognoz (trzeba, żeby Tkinter nie "zgubił" obrazów)
forecast_icons = []

def get_weather():
    city = city_entry.get()
    if not city:
        messagebox.showwarning("Błąd", "Wpisz nazwę miasta!")
        return

    params = {"q": city, "appid": API_KEY, "units": "metric", "lang": "pl"}

    try:
        # 🔹 Aktualna pogoda
        response = requests.get(CURRENT_URL, params=params)
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


        # 🔹 Ikona aktualnej pogody
        icon_url = f"https://openweathermap.org/img/wn/{icon_code}@2x.png"
        icon_response = requests.get(icon_url)
        icon_img = Image.open(BytesIO(icon_response.content)).convert("RGBA")
        icon_img = icon_img.resize((175, 175), Image.LANCZOS)

        icon_photo = ImageTk.PhotoImage(icon_img)
        icon_label.config(image=icon_photo)
        icon_label.image = icon_photo

        # 🔹 Prognoza godzinowa na 24h (8 * 3h)
        forecast_response = requests.get(FORECAST_URL, params=params)
        forecast_data = forecast_response.json()

        # Czyścimy poprzednią prognozę
        for widget in forecast_inner_frame.winfo_children():
            widget.destroy()
        forecast_icons.clear()

        for i in range(8):
            forecast = forecast_data["list"][i]
            time = forecast["dt_txt"].split()[1][:5]
            temp_f = forecast["main"]["temp"]
            desc_f = forecast["weather"][0]["description"].capitalize()
            icon_code_f = forecast["weather"][0]["icon"]

            # Pobranie ikony
            icon_url_f = f"https://openweathermap.org/img/wn/{icon_code_f}@2x.png"
            icon_response_f = requests.get(icon_url_f)
            icon_img_f = Image.open(BytesIO(icon_response_f.content)).convert("RGBA")
            icon_photo_f = ImageTk.PhotoImage(icon_img_f)

            # Trzymamy referencję do ikony
            forecast_icons.append(icon_photo_f)

            # Kolumna prognozy
            col_frame = tk.Frame(forecast_inner_frame, bg="lightblue")
            col_frame.grid(row=0, column=i, padx=5)

            tk.Label(col_frame, text=time, bg="lightblue", font=("Arial", 10, "bold")).pack()
            icon_label_f = tk.Label(col_frame, image=icon_photo_f, bg="lightblue")
            icon_label_f.pack()
            tk.Label(col_frame, text=f"{temp_f}°C", bg="lightblue", font=("Arial", 10)).pack()
            tk.Label(col_frame, text=desc_f, bg="lightblue", font=("Arial", 8), wraplength=80, justify="center").pack()

        # Aktualizacja scrollregion
        forecast_inner_frame.update_idletasks()
        forecast_canvas.config(scrollregion=forecast_canvas.bbox("all"))

    except Exception as e:
        messagebox.showerror("Błąd", f"Wystąpił problem:\n{e}")

# 🪟 GUI
root = tk.Tk()
root.title("Aplikacja pogodowa")
root.geometry("650x700")
root.resizable(False, False)
root.configure(bg="lightblue")

title_label = tk.Label(root, text="Sprawdź pogodę", font=("Arial", 16, "bold"), bg="lightblue")
title_label.pack(pady=10)

city_entry = tk.Entry(root, font=("Arial", 12))
city_entry.pack(pady=5)

search_button = tk.Button(root, text="Pobierz pogodę", command=get_weather, bg="blue", fg="white")
search_button.pack(pady=5)

icon_label = tk.Label(root, bg="lightblue")
icon_label.pack()

city_label = tk.Label(root, font=("Arial", 16, "bold"), bg="lightblue")
city_label.pack()

weather_label = tk.Label(root, font=("Arial", 13), bg="lightblue")
weather_label.pack(pady=5)


# 🔹 Canvas + Scrollbar dla prognozy z niebieskim tłem
forecast_canvas = tk.Canvas(root, bg="lightblue", height=180, highlightthickness=0)
forecast_scrollbar = tk.Scrollbar(
    root,
    orient="horizontal",
    command=forecast_canvas.xview,
    bg="lightblue",
    troughcolor="lightblue",
    highlightthickness=0
)
forecast_canvas.configure(xscrollcommand=forecast_scrollbar.set)

# --- OBSŁUGA KÓŁKA MYSZKI DO POZIOMEGO SCROLLA (Windows / macOS / Linux) ---
def _on_mousewheel_windows_mac(event):
    # event.delta jest wielokrotnością 120 na Windowsie; na macOS może być mniejsze
    # zamieniamy to na liczbę "units" do przewinięcia (1 = jedno "kliknięcie" kółka)
    delta = 0
    try:
        delta = int(event.delta / 120)
    except Exception:
        # jeśli event.delta ma małą wartość (np. macOS), użyjemy znaku
        delta = 1 if event.delta > 0 else -1
    # minus, bo chcemy: rolka w górę -> przesuwamy w lewo (negative -> left)
    forecast_canvas.xview_scroll(-delta, "units")

root.bind_all("<MouseWheel>", _on_mousewheel_windows_mac)

forecast_scrollbar.pack(side="bottom", fill="x")
forecast_canvas.pack(side="top", fill="both", expand=False)

forecast_inner_frame = tk.Frame(forecast_canvas, bg="lightblue")
forecast_canvas.create_window((0,0), window=forecast_inner_frame, anchor="nw")

root.mainloop()
