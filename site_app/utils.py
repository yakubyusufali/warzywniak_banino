import json
import smtplib
import os
import re

from django.conf import settings
from django.http import HttpRequest
from django.utils import timezone

from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from PIL import Image
from PIL.Image import Image as Img
from random import randint
from typing import Dict, Tuple, Any

from site_app import models


def prepare_new_item_list_data(data: Dict[str, str]) -> Dict[str, Dict[str, str]]:
    """
    Processes input data containing product name, data type and it's value to structured dictionary containing product
    names, and it's params values.

    Function filters input data, ignores technical keys, splits input keys into product names and data types, checks if
    product is already in created structured dictionary and ads it if not. Function ads values to those params for each
    product and returns structured dictionary containing all products and all values.

    :param data:
    A dictionary containing key in 'product_name-data_type' format and values of each parameter of each product.
    Contains also technical keys.

    :return:
    A structured dictionary of dictionaries, containing product names as a main key and a dictionary containing values
    of its params as a main key value.
    """
    new_data = {}
    for key in filter(lambda x: x != 'csrfmiddlewaretoken', data):
        item_name, data_type = key.split('-')
        if item_name not in new_data:
            new_data[item_name] = {}
        new_data[item_name][data_type] = data[key]
    return new_data


def check_item_quantity_correctness(quantity: str) -> str:
    """
    Cleans given str from white marks and checks if correctness. Str is correct if includes only digits and no more than
    one comma which isn't first or last sign of a str. Function returns white-marks-cleaned str if it's correct,
    otherwise it returns empty str.

    :param quantity:
    String to check.

    :return:
    White-marks-cleaned string if string is correct or empty string if isn't.
    """
    quantity = quantity.strip()
    pattern = '^[0-9]+(,[0-9]+)?$'
    if re.match(pattern, quantity):
        return quantity
    return ''


def prepare_raw_order_data(data: Dict[str, str]) -> tuple[Dict[str, float], list[str]]:
    """
    Processes input data containing orders to structured dictionary containing product names and their quantities.

    Function filters input data, ignores technical keys, checks remaining keys if their values are non-zero, generates
    product name by splitting param name on dash, checks inputted quantity correctness and cleans it from white marks.
    If data's correct, function converts it to float and stores  under the corresponding key in structured dictionary,
    if not, function adds corresponding product name to error list. Returns tule containing dict of correct order datas
    and error list.

    :param data:
    A dictionary of all product IDs and ordered product quantities. Contains also technical keys.

    :return:
    A structured dictionary of product-name-based keys and ordered quantities, cleaned from technical keys and
    non-ordered products.
    """
    order_data = {}
    errors = []
    for key in filter(lambda x: x not in ('csrfmiddlewaretoken', 'csrftoken', 'sessionid'), data):
        if data[key]:
            quantity_str = check_item_quantity_correctness(data[key])
            if quantity_str:
                quantity = convert_number_to_float(quantity_str)
                order_data[key] = quantity
            else:
                errors.append(key)
    return order_data, errors


def prepare_order_data(order_raw: Dict[str, float]) -> Tuple[Dict[Any, Dict[str, str | Any]], float, str]:
    """
    Prepares order data with all additional information, such as price, name, snakecase name, unit, quantity, sum of
    each product as well as delivery date and sum of an order.

    Function processes each item contained in raw order data, loads information of each product from database, rounds
    the number down if product is sold in pieces, counts a sum of each product, prepares order data for session usage,
    adds product sum to order sum and counts delivery date.

    :param order_raw:
    A structured dictionary contains ordered string products names and their float quantities.

    :return:
    A tuple contains:
        1. A structured dictionary contains ordered string products names and all additional information about each
           ordered product in second-level dictionary containing string keys and string values.
        2. A float number represents sum of an order.
        3. A datatime object represents delivery date of an order.
    """
    order_items = {}
    order_sum = float(0)
    delivery_today = True
    for item_name in order_raw:
        item = models.Item.objects.get(name_snakecase=item_name)
        item_quantity = order_raw[item_name]
        item_quantity_str = convert_number_to_str(item_quantity)
        item_sum = item_quantity // 1 * item.price if item.unit == 'szt.' else item_quantity * item.price
        order_items[item.name] = {
            'price': convert_number_to_str(item.price),
            'name': item.name,
            'name_snakecase': item.name_snakecase,
            'unit': item.unit,
            'quantity': item_quantity_str[:-3] if item_quantity % 1 == 0 or item.unit == 'szt.' else item_quantity_str,
            'item_sum': convert_number_to_str(item_sum),
            'delivery_days': item.delivery_days,
            'photo_url': item.photo_url,
        }
        order_sum += item_sum
        delivery_today = False if item.delivery_days else delivery_today
    order_delivery = set_delivery_date(delivery_today)
    return order_items, order_sum, order_delivery


def set_delivery_date(delivery_today: bool) -> str:
    """
    Decides if delivery is possible same day and returns delivery date of processed order.

    Function checks if delivery is possible same day (if it's before maximum order time and there are no products with
    next day delivery in basket). If no, it calls a function that returns next working day. Returns string
    representation of delivery date of an order.

    :param delivery_today:
    Boolean value containing information if all products in basket are with same-day delivery.

    :return:
    String representation of delivery date of an order in 'dd.mm.yyyy' format.
    """
    current_time = timezone.now()
    max_order_hour = 15
    max_order_minute = 30
    if (current_time.hour > max_order_hour or
            (current_time.hour == max_order_hour and current_time.minute > max_order_minute) or
            not delivery_today):
        order_delivery = find_next_work_day(current_time)
    else:
        order_delivery = current_time.date()
    return order_delivery.strftime("%d.%m.%Y")


def find_next_work_day(current_time: datetime) -> datetime:
    """
    Returns date of mext working day.

    Function prepares a table with all holidays in a specific year, then it checks day-by-day if it's a working day of
    a week and if it's not holiday. Returns date of first working, non-holidays day found.

    :param current_time:
    Datetime representation of current time.

    :return:
    Datetime representation of nearest working day date.
    """
    def first_day_easter(year: int) -> datetime:
        """
        Returns date of first day of easter on specific year.

        Function bases on a Carl Friedrich Gauss method of counting first day of easter. Function does not take into
        account exceptions for the years 2049 and 2076 and will make errors for these years.
        More: https://en.wikipedia.org/wiki/Date_of_Easter#Gauss's_Easter_algorithm

        :param year:
        Int representation of specific year.

        :return:
        Datetime representation of first day of Easter on a specific year.
        """
        a = ((year % 19) * 19 + 24) % 30
        b = (2 * (year % 4) + 4 * (year % 7) + 6 * a + 5) % 7
        return timezone.make_aware(datetime(year, 3, 22)) + timezone.timedelta(a + b)

    easter_1 = first_day_easter(current_time.date().year)
    easter_2 = easter_1 + timezone.timedelta(days=1)
    easter_61 = easter_1 + timezone.timedelta(days=60)
    holidays = [
        (1, 1),
        (6, 1),
        (1, 5),
        (3, 5),
        (15, 8),
        (1, 11),
        (11, 11),
        (25, 12),
        (26, 12),
        (easter_1.day, easter_1.month),
        (easter_2.day, easter_2.month),
        (easter_61.day, easter_61.month),
    ]
    date = current_time.date()
    work_day = False
    while not work_day:
        date = date + timezone.timedelta(days=1)
        if date.weekday() in (5, 6) or (date.day, date.month) in holidays:
            continue
        work_day = True
    return date


def send_email(subject: str, body: str, to_email: str) -> None:
    """
    Function send e-mail message.

    Function receives strings containing subject, body and receiver e-mail address and checks smtp server settings, than
    function formats a message containing received data, gets connection with smtp server and sends e-mail message. In
    case of connection problem, prints information in a console.

    :param subject:
    String containing message subject.

    :param body:
    String containing message body.

    :param to_email:
    String containing receiver e-mail address.

    :return:
    None
    """

    from_email = os.getenv('MAILBOX_USERNAME')
    password = os.getenv('MAILBOX_PASSWORD')
    smtp_server = os.getenv('MAILBOX_SMTP_SERVER')
    smtp_port = os.getenv('MAILBOX_SMTP_PORT')

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(from_email, password)
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
    except Exception:
        print(f"Error while sending e-mail: {Exception}")


def create_email_item_list(order_data: Dict[str, Dict[str, Any]]) -> str:
    """
    Part of e-mail sending process, formats string order item list.

    Function creates empty string, then for each product in order adds new line containing ordered item information to
    that string. Returns ready string.

    :param order_data:
    Structured dictionary containing string as a key, and second level structured dictionary containing string key and
    any-type value as a value.

    :return:
    String containing ordered product information.
    """
    item_list = ''
    for item_name, item_data in order_data.items():
        next_line = f'- {item_name}: {item_data['quantity']} {item_data['unit']} = {item_data['item_sum']} zł\n'
        item_list = item_list + next_line
    return item_list


def create_email_order_confirmation(
        user_data: Dict[str, str],
        order_data: Dict[str, Dict[str, Any]],
        order_sum: str,
        id: str,
        payment_method: str)\
        -> str:
    """
    Creates order confirmation e-mail message body.

    Function creates a message containing received order and user information data and returns a ready message string.

    :param user_data:
    Structured dictionary containing user data.

    :param order_data:
    Structured dictionary containing string as a key, and second level structured dictionary containing string key and
    any-type value as a value.

    :param order_sum:
    String representation of order sum.

    :param id:
    String representation of order id.

    :param payment_method:
    String containing chosen payment method information.

    :return:
    String containing order confirmation message body.
    """
    item_list = create_email_item_list(order_data)
    message = (
        f'Dziękujemy za złożenie zamówienia numer {id}.\n\n'
        f'Poniżej znajdziesz listę zamówionych artykułów:\n'
        f'{item_list}\n'
        f'Razem: {order_sum} zł.\n\n'
        f'Forma płatności: {payment_method}\n\n'
        f'Adres dostawy:\n'
        f'{user_data['street']} {user_data['house_number']}'
        f'{'/' + user_data['flat_number'] if user_data['flat_number'] else ''}\n'
        f'{user_data['city']}\n'
        f'Tel. {user_data['phone']}\n\n'
        f'{'Uwagi:\n' if user_data['comments'] else ''}'
        f'{user_data['comments'] if user_data['comments'] else ''}'
        f'{'\n\n' if user_data['comments'] else ''}'
        f'W razie potrzeby zapraszamy do kontaktu pod numerem 794 797 797.'
    )
    return message


def create_email_new_order(
        user_data: Dict[str, str],
        order_data: Dict[str, Dict[str, Any]],
        order_sum: str,
        id: str,
        payment_method: str)\
        -> str:
    """
    Creates new order notification e-mail message body.

    Function creates a message containing received order and user information data and returns a ready message string.

    :param user_data:
    Structured dictionary containing user data.

    :param order_data:
    Structured dictionary containing string as a key, and second level structured dictionary containing string key and
    any-type value as a value.

    :param order_sum:
    String representation of order sum.

    :param id:
    String representation of order id.

    :param payment_method:
    String containing chosen payment method information.

    :return:
    String containing new order notification e-mail message body.
    """
    item_list = create_email_item_list(order_data)
    message = (
        f"Złożono nowe zamówienie numer {id}.\n\n"
        f"Lista artykułów:\n"
        f"{item_list}\n"
        f"Suma: {(order_sum)} zł.\n\n"
        f"Forma płatności: {payment_method}\n\n"
        f"Adres dostawy:\n"
        f"{user_data['street']} {user_data['house_number']}"
        f"{'/' + user_data['flat_number'] if user_data['flat_number'] else ''}\n"
        f"{user_data['city']}\n"
        f"Tel. {user_data['phone']}\n\n"
        f"{'Uwagi:\n' if user_data['comments'] else ''}"
        f"{user_data['comments'] if user_data['comments'] else ''}"
    )
    return message


def crop_and_thumbnail_image(image: Img, thumbnail_size: tuple[int, int]) -> Img:
    """
    Thumbnails given image to square shape of requested size.

    Function checks if image is vertically or horizontally taken by counting a difference between its width and height.
    If difference is higher than zero (horizontal picture) functon cuts left and right margins, otherwise it cuts top
    and bottom parts of an image. If picture width is same as height, function doesn't cut it. After it squares a
    picture, function thumbnails a picture to given size

    :param image:
    PIL.Image.Image instance containing picture of a product.

    :param thumbnail_size:
    Tuple containing int representation of thumbnailed image width and height sizes.

    :return:
    PIL.Image.Image instance containing thumbnailed and squared picture of a product.
    """
    difference = image.width - image.height
    if difference > 0:
        borders = (
            difference / 2,
            0,
            image.width - difference / 2,
            image.height
        )
        image = image.crop(borders)
    elif difference < 0:
        difference = -difference
        borders = (
            0,
            difference / 2,
            image.width,
            image.height - difference / 2
        )
        image = image.crop(borders)
    image.thumbnail(thumbnail_size)
    return image


def make_relative_media_url(save_path: str) -> str:
    """
    Returns relative url for media.

    Function generates relative path containing media root path and save path, then adds it to project's media url.

    :param save_path:
    String containing save path.

    :return:
    String containing Relative media url.
    """
    relative_path = os.path.relpath(save_path, settings.MEDIA_ROOT)
    url = os.path.join(settings.MEDIA_URL, relative_path).replace("\\", "/")
    return url


def convert_name_to_snakecase(name: str) -> str:
    """
    Returns 'snakecased' string.

    Lowers and splits given string, then joins it with undercourse.

    :param name:
    Any string to be snakecased.

    :return:
    String containing snakecase version of given string.
    """
    return '_'.join(name.lower().split())


def format_and_capitalize_name(name: str) -> str:
    """
    Cleans and capitalizes given name of a product.

    Splits a name on white signs, then capitalizes each splitted part of a name and joins if with spaces.

    :param name:
    String to be cleaned and capitalized.

    :return:
    Capitalized version of given string.
    """
    return f'{' '.join(x.capitalize() for x in name.split())}'


def convert_number_to_str(price: float) -> str:
    """
    Converts number to string with a comma and two digits behind.

    Changes float to string with two digits after dot, than changes a dot by comma.

    :param price:
    Float representation of a price.

    :return:
    String representation of a price with dot changed to comma and two digits behind it.
    """
    return f'{price:.2f}'.replace('.', ',')


def convert_number_to_float(price: str) -> float:
    """
    Converts string number to float.

    Replaces comma with dot and changes type to float.

    :param price:
    String representation of a price.

    :return:
    Float representation of a price .
    """
    return float(price.replace(',', '.'))


def convert_str_date_to_datetime(str_date: str) -> datetime:
    """
    Returns datetime representation of given str date object (works with dd.mm.yyyy format).

    Function splits given string on dots and generates datetime object representing given date.

    :param str_date:
    Str date object in dd.mm.yyyy format.

    :return:
    Datetime object.
    """
    d, m, y = str_date.split('.')
    return timezone.datetime(int(y), int(m), int(d))


def generate_id() -> tuple[int, str]:
    """
    Generates unique and random order ID number.

    Function generates random int number between 1 and 1.000.000, then checks if generated ID is unique. If not,
    function adds 1 to generated ID number and checks againg. If yes, it generates 6-digits str version of ID with a
    dash between each half.

    :return:
    Function returns a tuple containing:
    - Int representation of generated ID number,
    - 6-digits str representation of ID number with a dash between each half.
    """
    id = randint(1, 1000000)
    id_is_unique = False
    while not id_is_unique:
        if models.Order.objects.filter(id=id).first():
            id = id + 1 if id < 999999 else 1
        else:
            id_is_unique = True
    id_str_raw = str(id).zfill(6)
    id_str = id_str_raw[:3] + '-' + id_str_raw[3:]
    return id, id_str


def add_new_order(request: HttpRequest, data: Dict) -> str:
    """
    Adds new order to database, sends email notification to the seller and email confirmation to the buyer - if wanted.

    Function runs order ID generator, from where it receives int and str representation of order ID. Then it loads from
    session json order data and turns it into dict. Function loads order sum from session and turns it to str. Then
    function adds new order record to database and sends e-mail notification to the shop. Function checks also if buyer
    e-mail address was given, and if yes, it sends order confirmation to the buyer.

    :param request:
    An object representing an HTTP request, containing data such as the HTTP method, headers, and parameters.

    :param data:
    Dict object containing order information, excluding ordered product list and order sum (e.g. delivery address,
    buyers contact data,payment method etc.)

    :return:
    Str representation of order ID.
    """
    id, id_str = generate_id()
    order_items_json = request.session['order_items']
    order_items = json.loads(order_items_json)
    order_sum = request.session['order_sum']
    order_sum_str = convert_number_to_str(order_sum)
    payment_method = data['payment_method']
    new_order = models.Order.objects.create(
        id=id,
        id_str=id_str,
        sum=order_sum,
        payment_method=payment_method,
        items=order_items_json,
        city=data['city'],
        street=data['street'],
        house_nr=data['house_number'],
        flat_nr=data['flat_number'],
        phone_number=data['phone'],
        email_address=data['email'],
        comments=data['comments'],
        completed=False,
        delivery_date=convert_str_date_to_datetime(request.session['order_delivery']),
    )
    send_email(
        subject=f"Nowe zamówienie - {data['city']}",
        body=create_email_new_order(data, order_items, order_sum_str, id_str, payment_method),
        to_email='yakub.yusufali@gmail.com'
    )
    if data['email']:
        send_email(
            subject=f"Potwierdzenie złożenia zamówienia",
            body=create_email_order_confirmation(data, order_items, order_sum_str, id_str, payment_method),
            to_email=data['email']
        )
    return id_str


def convert_user_data_to_json(data: Dict[str, Any]) -> str:
    """
        Converts user data from a dictionary to a JSON string.

        :param data:
        A dictionary containing user information.
        Expected keys are:
            - 'phone' (str): User's phone number.
            - 'street' (str): Street name.
            - 'house_number' (str): House number.
            - 'flat_number' (str): Flat/apartment number.
            - 'city' (str): City name.
            - 'email' (str): User's email address.
            - 'comments' (str): Additional comments about the user.

        :return:
        A JSON string containing the user's data with an additional field:
        'remember_data' set to True.
        """
    user_data = json.dumps({
        'phone': data['phone'],
        'street': data['street'],
        'house_number': data['house_number'],
        'flat_number': data['flat_number'],
        'city': data['city'],
        'email': data['email'],
        'comments': data['comments'],
        'remember_data': True,
    })
    return user_data


def save_photo_and_get_url(photo: Image) -> str:
    """
    Saves an uploaded photo to the server and returns its relative URL.

    :param photo:
    A file object containing the uploaded photo.

    :return:
    The relative URL of the saved photo within the media directory.
    """
    photo_filename = photo.name
    with Image.open(photo) as photo:
        photo = crop_and_thumbnail_image(photo, (150, 150))
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'photos'), exist_ok=True)
        save_path = os.path.join(settings.MEDIA_ROOT, 'photos', photo_filename).replace('\\', '/')
        photo.save(save_path)
    return make_relative_media_url(save_path)
