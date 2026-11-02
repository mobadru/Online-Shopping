
from django.urls import path

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import (
    CustomerRegistrationView,
    CustomerProfileView,
    ProductListView,
    ProductDetailView,

    # Shopping cart
    CartView,
    AddToCartView,
    CartItemDetailView,

    # Ordering
    CheckoutView,
    OrderHistoryView,
    OrderDetailView,
)


urlpatterns = [

    # =================================================
    # 1. AUTHENTICATION
    # =================================================

    path(
        'register/',
        CustomerRegistrationView.as_view(),
        name='register'
    ),

    path(
        'login/',
        TokenObtainPairView.as_view(),
        name='login'
    ),

    path(
        'token/refresh/',
        TokenRefreshView.as_view(),
        name='token_refresh'
    ),


    # =================================================
    # 2. CUSTOMER PROFILE
    # =================================================

    path(
        'profile/',
        CustomerProfileView.as_view(),
        name='profile'
    ),


    # =================================================
    # 3. PRODUCTS
    # =================================================

    path(
        'products/',
        ProductListView.as_view(),
        name='products'
    ),

    path(
        'products/<int:pk>/',
        ProductDetailView.as_view(),
        name='product_detail'
    ),


    # =================================================
    # 4. SHOPPING CART
    # =================================================

    path(
        'cart/',
        CartView.as_view(),
        name='cart'
    ),

    path(
        'cart/add/',
        AddToCartView.as_view(),
        name='cart_add'
    ),

    path(
        'cart/items/<int:item_id>/',
        CartItemDetailView.as_view(),
        name='cart_item_detail'
    ),


    # =================================================
    # 5. ORDERING
    # =================================================

    path(
        'orders/checkout/',
        CheckoutView.as_view(),
        name='checkout'
    ),

    path(
        'orders/',
        OrderHistoryView.as_view(),
        name='order_history'
    ),

    path(
        'orders/<uuid:checkout_reference>/',
        OrderDetailView.as_view(),
        name='order_detail'
    ),

]
