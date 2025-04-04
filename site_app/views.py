import json

from django import views
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import render, redirect
from django.utils import timezone

from decimal import Decimal
from site_app import models
from site_app import utils


class IndexView(views.View):
    """
    View for rendering the index page.
    """
    def get(self, request):
        """
        Renders the index page.

        :param request: HttpRequest object.

        :return: HttpResponse object rendering the index page.
        """
        return render(
            request,
            'site_app/index.html',
        )


class LoginView(views.View):
    """
    View for handling user login.
    """
    def get(self, request):
        """
        Renders the login page.

        :param request: HttpRequest object.

        :return: HttpResponse object rendering the login page.
        """
        return render(
            request,
            'site_app/login.html',
        )

    def post(self, request):
        """
        Handles user login form submission.

        1. Loads data from the POST form.
        2. Sets the user variable as None.
        3. Checks if a user with the given username exists in the database.
        4. If the user exists, checks if the password is correct; if not, reloads the login page.
        5. If the password is correct, logs the user in and redirects to the seller menu; if not, reloads the login page.

        :param request: HttpRequest object containing login form data.

        :return: HttpResponse object redirecting to the seller menu if login is successful, or reloads the login page.
        """
        data = request.POST
        user = None
        username = data['login']
        password = data['password']
        userdata = models.User.objects.filter(username=username).first()
        if userdata:
            user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('site_app:seller_menu')


class ItemListView(LoginRequiredMixin, views.View):
    """
    View for displaying and managing a list of items.
    """
    def get(self, request):
        """
        Displays a list of items (products) for management.

        1. Loads non-deleted items (products) data from the database, orders them alphabetically by name, and converts the data to a list.
        2. Converts the price of each product to a string.
        3. Loads the item list into the page context data.
        4. Renders the item list page (products manager).

        :param request: HttpRequest object.

        :return: HttpResponse object rendering the item list page.
        """
        items = list(models.Item.objects.filter(deleted=False).order_by('name'))
        context = {
            'items': items
        }
        return render(
            request,
            'site_app/item_list.html',
            context
        )

    def post(self, request):
        """
        Handles the form submission for updating item data.

        1. Loads data from the POST form.
        2. Prepares a dictionary containing the loaded items data.
        3. Loads each item's data from the prepared dictionary.
        4. Loads the data of each item from the database and overwrites the item data with the new data from the dictionary, then saves each item's data.
        5. Redirects back to the item list page (products manager).

        :param request: HttpRequest object containing item update data.

        :return: HttpResponse object redirecting to the item list page.
        """
        data = request.POST
        new_data = utils.prepare_new_item_list_data(data)
        for item_name in new_data:
            item_data = new_data[item_name]
            item = models.Item.objects.get(name_snakecase=item_name)
            item.name = utils.format_and_capitalize_name(item_data['name'])
            item.name_snakecase = utils.convert_name_to_snakecase(item_data['name'])
            item.price = Decimal(item_data['price'].replace(',', '.'))
            item.unit = item_data['unit']
            item.is_available = True if 'availability' in item_data else False
            item.delivery_days = 0 if item_data['delivery_date'] == 'today' else 1
            item.save()
        return redirect('site_app:item_list')


class ShopView(views.View):
    """
    View for displaying the shop page and handling order submissions.
    """
    def get(self, request):
        """
        Displays the shop page with a list of available products.

        1. Loads non-deleted items (products) data from the database, orders them alphabetically by name, and converts the data to a list.
        2. Converts the price of each product to a string.
        3. Loads the item list into the page context data.
        4. Renders the shopping page (product list).

        :param request: HttpRequest object.

        :return: HttpResponse object rendering the shop page.
        """
        items = models.Item.objects.filter(deleted=False).order_by('name')
        order_data_json = request.COOKIES.get('order')
        if order_data_json:
            order_data = json.loads(order_data_json)
        for item in items:
            item.quantity = order_data[item.name_snakecase] if order_data_json else ''
        context = {
            'items': items,
        }
        errors = [str(x) for x in messages.get_messages(request)]
        if errors:
            context['errors'] = errors
        res = render(
            request,
            'site_app/shop.html',
            context
        )
        res.delete_cookie('order')
        return res

    def post(self, request):
        """
        Handles the form submission for placing an order.

        1. Loads data from the POST form.
        2. Prepares a dictionary containing the raw loaded order data.
        3. Loads the data of each ordered product from the database and prepares a full product list, counts the order sum, and calculates the order delivery date.
        4. Saves the order data, order sum, and delivery date to the session.
        5. Redirects to the order confirmation page.

        :param request: HttpRequest object containing order data.

        :return: HttpResponse object redirecting to the order confirmation page or shop page with errors.
        """
        data = request.POST
        order_raw, errors = utils.prepare_raw_order_data(request, data)
        if errors:
            res = redirect('site_app:shop_view')
            res.set_cookie('order', json.dumps(data))
            return res
        else:
            order_items, order_sum, order_delivery = utils.prepare_order_data(order_raw)
            request.session['order_items'] = json.dumps(order_items)
            request.session['order_sum'] = order_sum
            request.session['order_delivery'] = order_delivery
            return redirect('site_app:order_confirmation_view')


class OrderConfirmationView(views.View):
    """
    View for displaying and handling order confirmation.
    """
    def get(self, request):
        """
        Displays the order confirmation page.

        1. Loads user data if it exists in cookies.
        2. Loads the order sum from the session.
        3. Loads the order data, order sum (converted to string), delivery date, and user data (if it exists) into the page context.
        4. Renders the order confirmation page.

        :param request: HttpRequest object.

        :return: HttpResponse object rendering the order confirmation page.
        """
        user_data = request.COOKIES.get('user_data')
        order_sum = request.session['order_sum']
        context = {
            'order': json.loads(request.session['order_items']),
            'sum': order_sum,
            'delivery': request.session['order_delivery'],
            'user_data': json.loads(user_data) if user_data else None,
        }
        return render(
            request,
            'site_app/order_confirmation.html',
            context
        )

    def post(self, request):
        """
        Handles the form submission for confirming an order.

        1. Loads data from the POST form.
        2. Saves the new order in the database and gets a string representation of the new order ID.
        3. Converts the user data to JSON.
        4. Prepares a response object.
        5. Saves the user data to cookies if the user chose to save it, or deletes the user data if they didn't.
        6. Loads the user data, payment method, and order ID into the session.
        7. Redirects to the order summary page.

        :param request: HttpRequest object containing order confirmation data.

        :return: HttpResponse object redirecting to the order summary page.
        """
        data = request.POST
        id_str = utils.add_new_order(request, data)
        user_data = utils.convert_user_data_to_json(data)
        res = redirect('site_app:order_summary')
        if 'remember-data' in data:
            res.set_cookie('user_data', user_data, max_age=60*60*24*365*2)
        else:
            res.delete_cookie('user_data')
        request.session['user_data'] = user_data
        request.session['payment_method'] = data['payment_method']
        request.session['id'] = id_str
        return res


class OrderSummaryView(views.View):
    """
    View for displaying the order summary.
    """
    def get(self, request):
        """
        Displays the order summary page.

        1. Loads data from the session into the page context.
        2. Cleans the session.
        3. Renders the order summary view.

        :param request: HttpRequest object.

        :return: HttpResponse object rendering the order summary page.
        """
        context = {
            'order': json.loads(request.session['order_items']),
            'sum': request.session['order_sum'],
            'user_data': json.loads(request.session['user_data']),
            'payment_method': request.session['payment_method'],
            'id': request.session['id'],
        }
        request.session.flush()
        return render(
            request,
            'site_app/order_summary.html',
            context
        )


class OrderListView(LoginRequiredMixin, views.View):
    """
    View for displaying a list of orders for management.
    """
    def get(self, request):
        """
        Displays a list of orders for management.

        1. Loads a filtered order list from the database (loads only not completed, today, or future orders) and orders it by delivery date.
        2. Loads each order's product list, order sum, order ID, and checks if the given order has today's delivery date.
        3. Loads the orders data into the page context.
        4. Renders the order list page.

        :param request: HttpRequest object.

        :return: HttpResponse object rendering the order list page.
        """
        orders = models.Order.objects\
            .filter(Q(completed=False) & Q(delivery_date__gte=timezone.now().date()))\
            .order_by('delivery_date')
        for single_order in orders:
            single_order.items = json.loads(single_order.items)
            single_order.id = single_order.id_str.replace('-', '')
            single_order.delivery_today = True if single_order.delivery_date == timezone.now().date() else False
        context = {
            'orders': orders,
        }
        return render(
            request,
            'site_app/order_list.html',
            context
        )


class AddItemView(LoginRequiredMixin, views.View):
    """
    View for adding new items.
    """
    def get(self, request):
        """
        Renders the add-item page.

        :param request: HttpRequest object.

        :return: HttpResponse object rendering the add-item page.
        """
        return render(
            request,
            'site_app/add_item.html',
        )

    def post(self, request):
        """
        Handles the form submission for adding a new item.

        1. Loads data from the POST form.
        2. Loads the uploaded photo file.
        3. Adds the new product to the database.
        4. Redirects back to the add-item page.

        :param request: HttpRequest object containing item data.

        :return: HttpResponse object redirecting to the add-item page.
        """
        data = request.POST
        photo = request.FILES.get('add_photo')
        new_item = models.Item.objects.create(
            name=utils.format_and_capitalize_name(data['name']),
            name_snakecase=utils.convert_name_to_snakecase(data['name']),
            price=Decimal(data['price'].replace(',', '.')),
            unit=data['unit'],
            delivery_days=0 if data['delivery_date'] == 'today' else 1,
            is_available=True if 'is_available' in data else False,
            deleted=False,
            photo_url=utils.save_photo_and_get_url(photo),
        )
        return redirect('site_app:add_item')


class DeleteItemView(LoginRequiredMixin, views.View):
    """
    View for deleting an item.
    """
    def get(self, request, item_id):
        """
        Displays the delete-item confirmation page.

        1. Loads item data from the database by the given item ID.
        2. Loads the item data into the page context.
        3. Renders the delete-item page.

        :param request: HttpRequest object.

        :param item_id: The ID of the item to delete.

        :return: HttpResponse object rendering the delete-item page.
        """
        item = models.Item.objects.get(id=item_id)
        context = {
            'item': item,
        }
        return render(
            request,
            'site_app/remove_item.html',
            context
        )

    def post(self, request, item_id):
        """
        Handles the form submission for deleting an item.

        1. Loads item data from the database by the given item ID.
        2. Changes the item-deleted status to True.
        3. Saves the changes in the database.
        4. Redirects to the item list page.

        :param request: HttpRequest object.

        :param item_id: The ID of the item to delete.

        :return: HttpResponse object redirecting to the item list page.
        """
        item = models.Item.objects.get(id=item_id)
        item.deleted = True
        item.save()
        return redirect('site_app:item_list')


class ChangePhotoView(LoginRequiredMixin, views.View):
    """
    View for changing an item's photo.
    """
    def get(self, request, item_id):
        """
        Displays the change-item-photo page.

        1. Loads item data from the database by the given item ID.
        2. Loads the item data into the page context.
        3. Renders the change-item-photo page.

        :param request: HttpRequest object.

        :param item_id: The ID of the item to change the photo for.

        :return: HttpResponse object rendering the change-item-photo page.
        """
        item = models.Item.objects.get(id=item_id)
        context = {
            'name': item.name,
            'photo_url': item.photo_url
        }
        return render(
            request,
            'site_app/change_photo.html',
            context
        )

    def post(self, request, item_id):
        """
        Handles the form submission for changing an item's photo.

        1. Loads item data from the database by the given item ID.
        2. Loads the uploaded photo file.
        3. Saves the new photo and gets its URL address.
        4. Saves the new photo URL to the item record in the database.
        5. Redirects to the item list page.

        :param request: HttpRequest object.

        :param item_id: The ID of the item to change the photo for.

        :return: HttpResponse object redirecting to the item list page.
        """
        item = models.Item.objects.get(id=item_id)
        photo = request.FILES.get('add_photo')
        photo_url = utils.save_photo_and_get_url(photo)
        item.photo_url = photo_url
        item.save()
        return redirect('site_app:item_list')


class SellerMenu(LoginRequiredMixin, views.View):
    """
    View for rendering the seller menu page.
    """
    def get(self, request):
        """
        Renders the seller actions menu page.

        :param request: HttpRequest object.

        :return: HttpResponse object rendering the seller menu page.
        """
        return render(
            request,
            'site_app/seller_menu.html',
        )


class LogoutView(LoginRequiredMixin, views.View):
    """
    View for handling user logout.
    """
    def get(self, request):
        """
        Renders the logout confirmation page.

        :param request: HttpRequest object.

        :return: HttpResponse object rendering the logout page.
        """
        return render(
            request,
            'site_app/logout.html',
        )

    def post(self, request):
        """
        Logs the user out and redirects to the shop page.

        1. Logs the user out.
        2. Redirects to the shop page.

        :param request: HttpRequest object.

        :return: HttpResponse object redirecting to the shop page.
        """
        logout(request)
        return redirect('site_app:shop_view')
