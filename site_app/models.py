from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models


class Item(models.Model):
    name = models.CharField(max_length=255)
    name_snakecase = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    unit = models.CharField(max_length=7)
    delivery_days = models.IntegerField()
    is_available = models.BooleanField()
    deleted = models.BooleanField(default=False)
    photo_url = models.CharField(max_length=256, default=None, null=True, blank=True)

    def __str__(self):
        return ('[DELETED] ' if self.deleted else '') + self.name


class Order(models.Model):
    id = models.IntegerField(primary_key=True, unique=True)
    id_str = models.CharField(max_length=7)
    sum = models.DecimalField(max_digits=6, decimal_places=2)
    payment_method = models.CharField(max_length=7, default='cash')
    items = models.CharField(max_length=8191)
    city = models.CharField(max_length=255)
    street = models.CharField(max_length=255)
    house_nr = models.CharField(max_length=7)
    flat_nr = models.CharField(max_length=7, null=True, blank=True, default=None)
    phone_number = models.CharField(max_length=15)
    email_address = models.EmailField()
    comments = models.CharField(max_length=511, default='')
    paid = models.BooleanField(default=False)
    completed = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateField()

    def __str__(self):
        return self.id_str
