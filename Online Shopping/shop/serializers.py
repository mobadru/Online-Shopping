
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction

from rest_framework import serializers

from .models import (
    Customer,
    Product,
    Category,
    Inventory,
    Cart,
    CartItem,
    Checkout,
    Order,
    OrderItem,
)

User = get_user_model()


# =====================================================
# 1. CUSTOMER REGISTRATION SERIALIZER
# Stored in the default database
# =====================================================

class CustomerRegistrationSerializer(serializers.Serializer):

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        min_length=8
    )
    phone = serializers.CharField(max_length=20)
    address = serializers.CharField(
        required=False,
        allow_blank=True
    )

    def validate_username(self, value):
        if User.objects.using('default').filter(
            username=value
        ).exists():
            raise serializers.ValidationError(
                "This username is already taken."
            )

        return value

    def validate_email(self, value):
        if User.objects.using('default').filter(
            email__iexact=value
        ).exists():
            raise serializers.ValidationError(
                "This email is already registered."
            )

        return value

    @transaction.atomic(using='default')
    def create(self, validated_data):

        user = User.objects.db_manager('default').create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )

        Customer.objects.using('default').create(
            user=user,
            phone=validated_data['phone'],
            address=validated_data.get('address', '')
        )

        return user

    def to_representation(self, instance):

        customer = Customer.objects.using('default').get(
            user_id=instance.id
        )

        return {
            'message': 'Customer registered successfully.',
            'customer': {
                'id': customer.id,
                'user_id': instance.id,
                'username': instance.username,
                'email': instance.email,
                'phone': customer.phone,
                'address': customer.address,
            }
        }


# =====================================================
# 2. CATEGORY SERIALIZER
# =====================================================

class CategorySerializer(serializers.ModelSerializer):

    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'description'
        ]


# =====================================================
# 3. PRODUCT SERIALIZER
# =====================================================

class ProductSerializer(serializers.ModelSerializer):

    category = CategorySerializer(read_only=True)

    stock_quantity = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'description',
            'category',
            'price',
            'image',
            'is_available',
            'stock_quantity',
            'created_at',
        ]

    def get_stock_quantity(self, obj):

        database = obj._state.db or 'dar'

        inventory = Inventory.objects.using(database).filter(
            product_id=obj.id
        ).first()

        return inventory.quantity if inventory else 0


# =====================================================
# 4. CART ITEM SERIALIZER
# CartItem is stored in the default database.
# Product and inventory are retrieved from its branch.
# =====================================================

class CartItemSerializer(serializers.ModelSerializer):

    product_name = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    stock_quantity = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem

        fields = [
            'id',
            'branch',
            'product_id',
            'product_name',
            'price',
            'image',
            'quantity',
            'stock_quantity',
            'line_total',
        ]

    def get_product(self, obj):

        return Product.objects.using(obj.branch).filter(
            id=obj.product_id,
            is_available=True
        ).first()

    def get_product_name(self, obj):

        product = self.get_product(obj)

        return product.name if product else 'Product unavailable'

    def get_price(self, obj):

        product = self.get_product(obj)

        return product.price if product else Decimal('0.00')

    def get_image(self, obj):

        product = self.get_product(obj)

        return product.image if product else None

    def get_stock_quantity(self, obj):

        inventory = Inventory.objects.using(obj.branch).filter(
            product_id=obj.product_id
        ).first()

        return inventory.quantity if inventory else 0

    def get_line_total(self, obj):

        price = self.get_price(obj)

        return price * obj.quantity


# =====================================================
# 5. SHOPPING CART SERIALIZER
# Stored in the default database.
# Can contain Dar and Zanzibar products.
# =====================================================

class CartSerializer(serializers.ModelSerializer):

    items = CartItemSerializer(many=True, read_only=True)

    total_items = serializers.SerializerMethodField()

    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Cart

        fields = [
            'id',
            'items',
            'total_items',
            'total_amount',
            'created_at',
            'updated_at',
        ]

    def get_total_items(self, obj):

        return sum(
            item.quantity
            for item in obj.items.all()
        )

    def get_total_amount(self, obj):

        total = Decimal('0.00')

        for item in obj.items.all():

            product = Product.objects.using(
                item.branch
            ).filter(
                id=item.product_id,
                is_available=True
            ).first()

            if product:
                total += product.price * item.quantity

        return total


# =====================================================
# 6. CHECKOUT SERIALIZER
# Stored in the default database.
# =====================================================

class CheckoutSerializer(serializers.ModelSerializer):

    username = serializers.CharField(
        source='user.username',
        read_only=True
    )

    class Meta:
        model = Checkout

        fields = [
            'id',
            'reference',
            'username',
            'total_amount',
            'delivery_address',
            'created_at',
        ]

        read_only_fields = fields


# =====================================================
# 7. ORDER ITEM SERIALIZER
# Stored in the branch database.
# =====================================================

class OrderItemSerializer(serializers.ModelSerializer):

    product_name = serializers.CharField(
        source='product.name',
        read_only=True
    )

    product_image = serializers.URLField(
        source='product.image',
        read_only=True,
        allow_null=True
    )

    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem

        fields = [
            'id',
            'product_id',
            'product_name',
            'product_image',
            'quantity',
            'unit_price',
            'subtotal',
        ]

        read_only_fields = fields

    def get_subtotal(self, obj):

        return obj.unit_price * obj.quantity


# =====================================================
# 8. ORDER SERIALIZER
# Stored in the selected branch database.
# =====================================================

class OrderSerializer(serializers.ModelSerializer):

    items = OrderItemSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = Order

        fields = [
            'id',
            'customer_id',
            'checkout_reference',
            'total_amount',
            'status',
            'delivery_address',
            'items',
            'created_at',
            'updated_at',
        ]

        read_only_fields = fields


# =====================================================
# END OF SERIALIZERS
# =====================================================
