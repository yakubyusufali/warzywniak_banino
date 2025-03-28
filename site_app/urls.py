from django.urls import path
from site_app import views
from django.conf import settings
from django.conf.urls.static import static

app_name = 'site_app'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('sklep/', views.ShopView.as_view(), name='shop_view'),
    path('login/', views.LoginView.as_view(), name='login_view'),
    path('zarzadzaj/', views.ItemListView.as_view(), name='item_list'),
    path('zamowienia/', views.OrderListView.as_view(), name='order_list'),
    path('zmien_zdjecie/<int:item_id>', views.ChangePhotoView.as_view(), name='change_photo'),
    path('dodaj_produkt/', views.AddItemView.as_view(), name='add_item'),
    path('usun_produkt/<int:item_id>', views.DeleteItemView.as_view(), name='delete_item'),
    path('zamowienie/', views.OrderConfirmationView.as_view(), name='order_confirmation_view'),
    path('podsumowanie/', views.OrderSummaryView.as_view(), name='order_summary'),
    path('menu/', views.SellerMenu.as_view(), name='seller_menu'),
    path('wyloguj/', views.LogoutView.as_view(), name='logout'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
