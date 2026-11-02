
import uuid

from django.db import models
from django.conf import settings


# =====================================================
# 1. PRODUCT CATEGORY
# Stored in the selected branch database
# =====================================================

class Category(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']


# =====================================================
# 2. PRODUCT
# Stored in the selected branch database
# =====================================================

class Product(models.Model):

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products'
    )

    name = models.CharField(
        max_length=200
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    image = models.URLField(
        blank=True,
        null=True
    )

    is_available = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']


# =====================================================
# 3. CUSTOMER PROFILE
# Stored ONLY in the default database
# Shared by both branches
# =====================================================

class Customer(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer_profile'
    )

    phone = models.CharField(
        max_length=20
    )

    address = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.user.username

    class Meta:
        ordering = ['-created_at']


# =====================================================
# 4. BRANCH INVENTORY
# Stored in the selected branch database
# =====================================================

class Inventory(models.Model):

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='inventory'
    )

    quantity = models.PositiveIntegerField(
        default=0
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['product'],
                name='unique_product_inventory'
            )
        ]

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"


# =====================================================
# 5. CUSTOMER ORDER
# Stored in the selected branch database
#
# customer_id refers to the shared Customer record
# in the DEFAULT database.
#
# checkout_reference connects orders from both branches.
# =====================================================

class Order(models.Model):

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    customer_id = models.PositiveBigIntegerField(
        db_index=True,
        help_text='ID of the shared customer in the default database.'
    )

    checkout_reference = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Shared checkout reference connecting branch orders.'
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    delivery_address = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"Order #{self.id}"

    class Meta:
        ordering = ['-created_at']


# =====================================================
# 6. ORDER ITEMS
# Stored in the same branch database as Order
# =====================================================

class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT
    )

    quantity = models.PositiveIntegerField()

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


# =====================================================
# 7. SHARED CHECKOUT
# Stored ONLY in the default database
#
# Connects orders from Dar es Salaam and Zanzibar.
# =====================================================

class Checkout(models.Model):

    reference = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='checkouts'
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00
    )

    delivery_address = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"Checkout {self.reference}"

    class Meta:
        ordering = ['-created_at']


# =====================================================
# 8. SHARED SHOPPING CART
# Stored ONLY in the default database
# =====================================================

class Cart(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shopping_cart'
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"Cart - {self.user.username}"


# =====================================================
# 9. SHARED CART ITEMS
# Stored ONLY in the default database
# =====================================================

class CartItem(models.Model):

    BRANCH_CHOICES = [
        ('dar', 'Dar es Salaam'),
        ('zanzibar', 'Zanzibar'),
    ]

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )

    branch = models.CharField(
        max_length=20,
        choices=BRANCH_CHOICES
    )

    # Product belongs to either Dar or Zanzibar database.
    # Therefore, we store its ID instead of using a ForeignKey.
    product_id = models.PositiveBigIntegerField()

    quantity = models.PositiveIntegerField(
        default=1
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['cart', 'branch', 'product_id'],
                name='unique_cart_branch_product'
            )
        ]
        ordering = ['created_at']

    def __str__(self):
        return f"Cart Item - {self.product_id} ({self.branch})"



# =====================================================
# END OF SHOP MODELS
# =====================================================
