from flask import Flask, render_template, request
import requests
from pymongo import MongoClient

app = Flask(__name__)

# Настройка MongoDB
client = MongoClient('mongodb://localhost:27017/')  # Замените на ваш URI
db = client['traffic_data']  # Имя вашей базы данных
collection = db['traffic_info']  # Имя вашей коллекции

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def button_clicked():
    # Ваш API ключ Google Maps
    api_key = ''

    # Начальная и конечная точки маршрута
    origin_name = request.form['user_input_1']
    destination_name = request.form['user_input_2']

    def get_coordinates(place_name):
        # Добавляем параметр components для фильтрации по Казахстану
        url = f'https://maps.googleapis.com/maps/api/geocode/json?address={place_name}&components=country:KZ|administrative_area:Astana&key={api_key}'
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'OK':
                location = data['results'][0]['geometry']['location']
                return location['lat'], location['lng']
            else:
                return None, None
        else:
            return None, None

    # Получение координат для начальной и конечной точки
    origin_coords = get_coordinates(origin_name)
    destination_coords = get_coordinates(destination_name)

    if origin_coords and destination_coords:
        # Преобразуем кортежи координат в строку
        origin = f"{origin_coords[0]},{origin_coords[1]}"
        destination = f"{destination_coords[0]},{destination_coords[1]}"
    else:
        return "Не удалось найти одну или обе точки. Пожалуйста, проверьте ввод."

    # Формирование URL запроса для маршрута
    url = f'https://maps.googleapis.com/maps/api/directions/json?origin={origin}&destination={destination}&key={api_key}&traffic_model=best_guess&departure_time=now&language=ru'

    # Выполнение запроса
    response = requests.get(url)

    # Проверка успешности запроса
    if response.status_code == 200:
        data = response.json()

        # Обработка данных о загруженности
        if 'routes' in data and len(data['routes']) > 0:
            for route in data['routes']:
                legs = route.get('legs', [])
                for leg in legs:
                    steps_info = []
                    for step in leg['steps']:
                        steps_info.append({
                            'инструкция': step['html_instructions'],
                            'дистанция': step['distance']['text'],
                            'продолжительность': step['duration']['text']
                        })
                    
                    traffic_data = {
                        'Начало': origin_name,
                        'Место назначения': destination_name,
                        'Длительность': leg['duration']['text'],
                        'Продолжительность в пробке': leg['duration_in_traffic']['text'],
                        'Расстояние': leg['distance']['text'],
                        'Шаги': steps_info
                    }
                
                    # Вставка данных в MongoDB
                    collection.insert_one(traffic_data)
                    
            # После сохранения данных, перенаправляем пользователя на страницу с результатами
            return "Данные успешно сохранены в MongoDB! <a href='/submit/result'>Перейти к результату</a>"
        else:
            return "Нет доступных маршрутов для указанных координат."
    else:
        print('Ошибка при выполнении запроса:', response.status_code)
        return "Ошибка при получении данных от Google Maps."
    
@app.route('/submit/result', methods=['GET'])
def result():
    saved_data = list(collection.find().sort('_id', -1).limit(1))  # Получаем только последнюю запись
    return render_template('result.html', saved_data=saved_data)

if __name__ == "__main__":
    app.run(debug=True)
