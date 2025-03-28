import json

from django import views
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import render, redirect
from django.utils import timezone

from site_app import models
from site_app import utils


class IndexView(views.View):
    def get(self, request):
        """
        Renders ndex page.
        """
        return render(
            request,
            'site_app/index.html',
        )

class LoginView(views.View):
    def get(self, request):
        """
        Renders login page
        """
        return render(
            request,
            'site_app/login.html',
        )

    def post(self, request):
        """
        1. Loads data from POST form,
        2. Sets user variable as None,
        3. Checks, if user with given username exists in database,
        4. If user exists, checks if password is correct, if user doesn't exist, reloads login page,
        5. If password is correct, logs the user in and redirects to seller menu, if password is incorrect, reloads
            login page,
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
    def get(self, request):
        """
        1. Loads non-deleted items (products) data from database, orders items alphabetically by its name and converts
            data to list type.
        2. Converts price of each product to str type,
        3. Loads item list to page context data,
        4. Renders item list page (products manager).
        """
        items = list(models.Item.objects.filter(deleted=False).order_by('name'))
        for item in items:
            item.price = utils.convert_number_to_str(item.price)
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
        1. Loads data prom POST form,
        2. Prepares dict containing loaded items data,
        3. Loads each item data from prepared dict,
        4. Loads data of each item from database and overwrites item data with new data from dict, then saves each item
            data.
        5. Redirects back to item list page (products manager).
        """
        data = request.POST
        new_data = utils.prepare_new_item_list_data(data)
        for item_name in new_data:
            item_data = new_data[item_name]
            item = models.Item.objects.get(name_snakecase=item_name)
            item.name = utils.format_and_capitalize_name(item_data['name'])
            item.name_snakecase = utils.convert_name_to_snakecase(item_data['name'])
            item.price = utils.convert_number_to_float(item_data['price'])
            item.unit = item_data['unit']
            item.is_available = True if 'availability' in item_data else False
            item.delivery_days = 0 if item_data['delivery_date'] == 'today' else 1
            item.save()
        return redirect('site_app:item_list')


class ShopView(views.View):
    def get(self, request):
        """
        1. Loads non-deleted items (products) data from database, orders items alphabetically by its name and converts
            data to list type.
        2. Converts price of each product to str type,
        3. Loads item list to page context data,
        4. Renders shopping page (product list).
        """
        items = models.Item.objects.filter(deleted=False).order_by('name')
        for item in items:
            item.price = utils.convert_number_to_str(item.price)
        context = {
            'items': items,
        }
        errors = request.COOKIES.get('errors')
        if errors:
            order_data = request.COOKIES.get('order')
            context['errors'] = errors
            context['order'] = order_data
            print(errors)
            print(order_data)
        res = render(
            request,
            'site_app/shop.html',
            context
        )
        res.delete_cookie('errors')
        res.delete_cookie('order')
        return res

    def post(self, request):
        """
        1. Loads data prom POST form,
        2. Prepares dict containing raw loaded order data,
        3. Loads data of each ordered product from database and prepares full product list, counts order sum and order
            delivery date,
        4. Saves order data, order sum and delivery date to session,
        5. Redirects to order confirmation page.
        """
        data = request.POST
        order_raw, errors = utils.prepare_raw_order_data(data)
        if errors:
            loaded_data = {}
            for record in data:
                loaded_data[record.split('-')[0]] = data[record]
            res = redirect('site_app:shop_view')
            res.set_cookie('errors', json.dumps(errors))
            res.set_cookie('order', json.dumps(loaded_data))
            return res
        else:
            order_items, order_sum, order_delivery = utils.prepare_order_data(order_raw)
            request.session['order_items'] = json.dumps(order_items)
            request.session['order_sum'] = order_sum
            request.session['order_delivery'] = order_delivery
            return redirect('site_app:order_confirmation_view')


class OrderConfirmationView(views.View):
    def get(self, request):
        """
        1. Loads user data if exists in cookies,
        2. Loads order sum from session,
        3. Loads order data, order sum (converted to str), delivery date and user data (if exists) to page context,
        4. Renders order confirmation page.
        """
        user_data = request.COOKIES.get('user_data')
        order_sum = request.session['order_sum']
        context = {
            'order': json.loads(request.session['order_items']),
            'sum': utils.convert_number_to_str(order_sum),
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
        1. Loads data from POST form,
        2. Saves new order in database and gets str representation of new order ID,
        3. Converts user data to JSON,
        4. Prepares response object,
        5. Saves user data to cookies if the user chose to save it or deletes the user data if they didn't,
        6. Loads user data, payment method and order ID to session,
        7. Redirects to order summary page.
        """
        data = request.POST
        order_id_str = utils.add_new_order(request, data)
        user_data = utils.convert_user_data_to_json(data)
        res = redirect('site_app:order_summary')
        if 'remember-data' in data:
            res.set_cookie('user_data', user_data, max_age=60*60*24*365*2)
        else:
            res.delete_cookie('user_data')
        request.session['user_data'] = user_data
        request.session['payment_method'] = data['payment_method']
        request.session['order_id'] = order_id_str
        return res


class OrderSummaryView(views.View):
    def get(self, request):
        """
        1. Loads data from session to page context,
        2. Cleans session,
        3. Renders order summary view.
        """
        context = {
            'order': json.loads(request.session['order_items']),
            'sum': request.session['order_sum'],
            'user_data': json.loads(request.session['user_data']),
            'payment_method': request.session['payment_method'],
            'order_id': request.session['order_id'],
        }
        request.session.flush()
        return render(
            request,
            'site_app/order_summary.html',
            context
        )


class OrderListView(LoginRequiredMixin, views.View):
    def get(self, request):
        """
        1. Loads filtered order list from database (loads only not completed, today or future orders) and orders it by
            delivery date,
        2. Loads each order product list, order sum, order ID and checks if given order has today's delivery date,
        3. Load orders data to page context,
        4. Renders order list page.
        """
        orders = models.Order.objects\
            .filter(Q(completed=False) & Q(delivery_date__gte=timezone.now().date()))\
            .order_by('delivery_date')
        for single_order in orders:
            single_order.items = json.loads(single_order.items)
            single_order.sum = str(single_order.sum).replace('.', ',')
            single_order.order_id = single_order.order_id_str.replace('-', '')
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
    def get(self, request):
        """
        Renders add-item page.
        """
        return render(
            request,
            'site_app/add_item.html',
        )

    def post(self, request):
        """
        1. Loads data from POST form,
        2. Loads uploaded photo file,
        3. Adds new product to database,
        4. Redirects back to add-item page.
        """
        data = request.POST
        photo = request.FILES.get('add_photo')
        new_item = models.Item.objects.create(
            name=utils.format_and_capitalize_name(data['name']),
            name_snakecase=utils.convert_name_to_snakecase(data['name']),
            price=float(data['price'].replace(',', '.')),
            unit=data['unit'],
            delivery_days=0 if data['delivery_date'] == 'today' else 1,
            is_available=True if 'is_available' in data else False,
            deleted=False,
            photo_url=utils.save_photo_and_get_url(photo),
        )
        return redirect('site_app:add_item')


class DeleteItemView(LoginRequiredMixin, views.View):
    def get(self, request, item_id):
        """
        1. Loads item data from database by given item ID,
        2. Loads item data to page context,
        3. Renders delete-item page.
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
        1. Loads item data from database by given item ID,
        2. Changes item-deleted status into True,
        3. Save changes in database,
        4. Redirects to item list page.
        """
        item = models.Item.objects.get(id=item_id)
        item.deleted = True
        item.save()
        return redirect('site_app:item_list')


class ChangePhotoView(LoginRequiredMixin, views.View):
    def get(self, request, item_id):
        """
        1. Loads item data from database by given item ID,
        2. Loads item data to page context,
        3. Renders change-item-photo page.
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
        1. Loads item data from database by given item ID,
        2. Loads uploaded photo file,
        3. Saves new photo and gets it URL address,
        4. Saves new photo URL to item record in database,
        5. Redirects to item list page.
        """
        item = models.Item.objects.get(id=item_id)
        photo = request.FILES.get('add_photo')
        photo_url = utils.save_photo_and_get_url(photo)
        item.photo_url = photo_url
        item.save()
        return redirect('site_app:item_list')


class SellerMenu(LoginRequiredMixin, views.View):
    def get(self, request):
        """
        Renders seller actions menu page.
        """
        return render(
            request,
            'site_app/seller_menu.html',
        )


class LogoutView(LoginRequiredMixin, views.View):
    def get(self, request):
        """
        Renders logout page.
        """
        return render(
            request,
            'site_app/logout.html',
        )

    def post(self, request):
        """
        1. Logs the user out,
        2. Redirects to shop page.
        """
        logout(request)
        return redirect('site_app:shop_view')
