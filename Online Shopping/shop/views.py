
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import (
    Product,
    Customer,
    Inventory,
    Cart,
    CartItem,
    Checkout,
    Order,
    OrderItem,
)

from .serializers import (
    CustomerRegistrationSerializer,
    ProductSerializer,
    CartSerializer,
    CheckoutSerializer,
    OrderSerializer,
)


# =====================================================
# DATABASE SELECTION
# =====================================================

DATABASE_BRANCHES = {
    'dar': 'dar',
    'zanzibar': 'zanzibar',
}


# =====================================================
# COMMON HELPERS
# =====================================================

def get_customer_cart(user):
    """
    Get or create the customer's shared cart.
    Stored in shared_customer_db.
    """

    cart, created = Cart.objects.using('default').get_or_create(
        user_id=user.id
    )

    return cart


def get_branch_product(branch, product_id):
    """
    Retrieve a product and its stock from the selected branch.
    """

    database = DATABASE_BRANCHES.get(branch)

    if database is None:
        raise ValidationError({
            'branch': 'Choose either dar or zanzibar.'
        })

    product = Product.objects.using(database).filter(
        id=product_id,
        is_available=True
    ).first()

    if product is None:
        raise ValidationError({
            'product': 'Product not found or unavailable.'
        })

    inventory = Inventory.objects.using(database).filter(
        product_id=product.id
    ).first()

    stock_quantity = inventory.quantity if inventory else 0

    return product, inventory, stock_quantity


def serialize_branch_order(order, branch):
    """
    Serialize an order using its own branch database.
    """

    serializer = OrderSerializer(order)

    data = dict(serializer.data)
    data['branch'] = branch

    return data


def get_checkout_orders(checkout_reference):
    """
    Retrieve all branch orders belonging to one checkout.
    """

    result = []

    for branch, database in DATABASE_BRANCHES.items():

        orders = Order.objects.using(database).filter(
            checkout_reference=checkout_reference
        ).order_by('id')

        for order in orders:
            result.append(
                serialize_branch_order(order, branch)
            )

    return result


def restore_branch_order_stock(database, order_id):
    """
    Compensate for a previously committed branch order
    if a later branch fails during checkout.
    """

    with transaction.atomic(using=database):

        order = Order.objects.using(database).filter(
            id=order_id
        ).first()

        if order is None:
            return

        order_items = list(
            OrderItem.objects.using(database).filter(
                order_id=order_id
            )
        )

        for item in order_items:

            inventory = Inventory.objects.using(database).filter(
                product_id=item.product_id
            ).first()

            if inventory:
                Inventory.objects.using(database).filter(
                    id=inventory.id
                ).update(
                    quantity=F('quantity') + item.quantity
                )

        order.delete()


# =====================================================
# 1. CUSTOMER REGISTRATION
# =====================================================

class CustomerRegistrationView(generics.CreateAPIView):

    serializer_class = CustomerRegistrationSerializer
    permission_classes = [AllowAny]


# =====================================================
# 2. CUSTOMER PROFILE
# =====================================================

class CustomerProfileView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        try:

            customer = Customer.objects.using('default').get(
                user_id=request.user.id
            )

            return Response({
                'id': customer.id,
                'user_id': request.user.id,
                'username': request.user.username,
                'email': request.user.email,
                'phone': customer.phone,
                'address': customer.address,
            })

        except Customer.DoesNotExist:

            return Response(
                {'error': 'Customer profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )


# =====================================================
# 3. PRODUCT LIST
# =====================================================

class ProductListView(generics.ListAPIView):

    serializer_class = ProductSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):

        branch = self.request.query_params.get(
            'branch', 'dar'
        ).lower()

        database = DATABASE_BRANCHES.get(branch)

        if database is None:
            raise ValidationError({
                'branch': 'Choose either dar or zanzibar.'
            })

        return (
            Product.objects.using(database)
            .filter(is_available=True)
            .select_related('category')
        )


# =====================================================
# 4. PRODUCT DETAILS
# =====================================================

class ProductDetailView(generics.RetrieveAPIView):

    serializer_class = ProductSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):

        branch = self.request.query_params.get(
            'branch', 'dar'
        ).lower()

        database = DATABASE_BRANCHES.get(branch)

        if database is None:
            raise ValidationError({
                'branch': 'Choose either dar or zanzibar.'
            })

        return (
            Product.objects.using(database)
            .filter(is_available=True)
            .select_related('category')
        )


# =====================================================
# 5. VIEW SHOPPING CART
#
# GET /api/auth/cart/
# =====================================================

class CartView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        cart = get_customer_cart(request.user)

        serializer = CartSerializer(cart)

        return Response(serializer.data)


# =====================================================
# 6. ADD PRODUCT TO CART
#
# POST /api/auth/cart/add/
# =====================================================

class AddToCartView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        branch = str(
            request.data.get('branch', '')
        ).lower()

        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)

        if branch not in DATABASE_BRANCHES:
            raise ValidationError({
                'branch': 'Choose either dar or zanzibar.'
            })

        try:
            product_id = int(product_id)
            quantity = int(quantity)

            if product_id <= 0 or quantity <= 0:
                raise ValueError

        except (TypeError, ValueError):
            raise ValidationError({
                'quantity': 'Product ID and quantity must be positive integers.'
            })

        database = DATABASE_BRANCHES[branch]

        product, inventory, stock_quantity = get_branch_product(
            branch,
            product_id
        )

        if stock_quantity < quantity:
            raise ValidationError({
                'stock': f'Only {stock_quantity} units are available.'
            })

        with transaction.atomic(using='default'):

            cart = Cart.objects.using('default').select_for_update().get_or_create(
                user_id=request.user.id
            )[0]

            cart_item = CartItem.objects.using('default').filter(
                cart_id=cart.id,
                branch=branch,
                product_id=product.id
            ).first()

            if cart_item:

                new_quantity = cart_item.quantity + quantity

                if new_quantity > stock_quantity:
                    raise ValidationError({
                        'stock': (
                            f'Only {stock_quantity} units are available '
                            'in total.'
                        )
                    })

                cart_item.quantity = new_quantity
                cart_item.save(update_fields=[
                    'quantity',
                    'updated_at'
                ])

            else:

                CartItem.objects.using('default').create(
                    cart_id=cart.id,
                    branch=branch,
                    product_id=product.id,
                    quantity=quantity
                )

            cart.save(update_fields=['updated_at'])

        cart = Cart.objects.using('default').get(
            id=cart.id
        )

        return Response({
            'message': 'Product added to cart successfully.',
            'cart': CartSerializer(cart).data
        }, status=status.HTTP_200_OK)


# =====================================================
# 7. UPDATE OR REMOVE CART ITEM
#
# PATCH /api/auth/cart/items/<item_id>/
# DELETE /api/auth/cart/items/<item_id>/
# =====================================================

class CartItemDetailView(APIView):

    permission_classes = [IsAuthenticated]

    def get_cart_item(self, request, item_id):

        cart_item = CartItem.objects.using('default').filter(
            id=item_id,
            cart__user_id=request.user.id
        ).first()

        if cart_item is None:
            raise ValidationError({
                'cart_item': 'Cart item not found.'
            })

        return cart_item

    def patch(self, request, item_id):

        cart_item = self.get_cart_item(
            request,
            item_id
        )

        try:
            quantity = int(request.data.get('quantity'))

            if quantity <= 0:
                raise ValueError

        except (TypeError, ValueError):
            raise ValidationError({
                'quantity': 'Quantity must be a positive integer.'
            })

        product, inventory, stock_quantity = get_branch_product(
            cart_item.branch,
            cart_item.product_id
        )

        if quantity > stock_quantity:
            raise ValidationError({
                'stock': f'Only {stock_quantity} units are available.'
            })

        cart_item.quantity = quantity

        cart_item.save(update_fields=[
            'quantity',
            'updated_at'
        ])

        cart = Cart.objects.using('default').get(
            id=cart_item.cart_id
        )

        cart.save(update_fields=['updated_at'])

        return Response({
            'message': 'Cart quantity updated successfully.',
            'cart': CartSerializer(cart).data
        })

    def delete(self, request, item_id):

        cart_item = self.get_cart_item(
            request,
            item_id
        )

        cart_id = cart_item.cart_id

        cart_item.delete()

        cart = Cart.objects.using('default').get(
            id=cart_id
        )

        cart.save(update_fields=['updated_at'])

        return Response({
            'message': 'Product removed from cart.',
            'cart': CartSerializer(cart).data
        })


# =====================================================
# 8. CHECKOUT
#
# POST /api/auth/orders/checkout/
# =====================================================

class CheckoutView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        delivery_address = request.data.get(
            'delivery_address'
        )

        if not delivery_address or not str(delivery_address).strip():
            raise ValidationError({
                'delivery_address': 'Delivery address is required.'
            })

        delivery_address = str(delivery_address).strip()

        customer = Customer.objects.using('default').filter(
            user_id=request.user.id
        ).first()

        if customer is None:
            raise ValidationError({
                'customer': 'Customer profile not found.'
            })

        # Lock the shared cart while preparing checkout.
        with transaction.atomic(using='default'):

            cart = Cart.objects.using('default').select_for_update().filter(
                user_id=request.user.id
            ).first()

            if cart is None:
                raise ValidationError({
                    'cart': 'Shopping cart not found.'
                })

            cart_items = list(
                CartItem.objects.using('default').select_for_update().filter(
                    cart_id=cart.id
                ).order_by('id')
            )

            if not cart_items:
                raise ValidationError({
                    'cart': 'Your shopping cart is empty.'
                })

            branch_items = {
                'dar': [],
                'zanzibar': [],
            }

            for item in cart_items:

                if item.branch not in branch_items:
                    raise ValidationError({
                        'cart': 'Cart contains an invalid branch.'
                    })

                branch_items[item.branch].append(item)

            branch_items = {
                branch: items
                for branch, items in branch_items.items()
                if items
            }

            checkout = Checkout.objects.using('default').create(
                user_id=request.user.id,
                total_amount=Decimal('0.00'),
                delivery_address=delivery_address
            )

            checkout_reference = checkout.reference

        created_orders = []
        checkout_total = Decimal('0.00')

        try:

            # Create one order for every branch represented in the cart.
            for branch, items in branch_items.items():

                database = DATABASE_BRANCHES[branch]

                with transaction.atomic(using=database):

                    validated_items = []
                    branch_total = Decimal('0.00')

                    # Validate products and lock inventory rows.
                    for cart_item in items:

                        product = Product.objects.using(
                            database
                        ).filter(
                            id=cart_item.product_id,
                            is_available=True
                        ).first()

                        if product is None:
                            raise ValidationError({
                                'product': (
                                    f'Product {cart_item.product_id} '
                                    f'is unavailable in {branch}.'
                                )
                            })

                        inventory = Inventory.objects.using(
                            database
                        ).select_for_update().filter(
                            product_id=product.id
                        ).first()

                        available_stock = (
                            inventory.quantity if inventory else 0
                        )

                        if available_stock < cart_item.quantity:
                            raise ValidationError({
                                'stock': (
                                    f'{product.name} has only '
                                    f'{available_stock} units available '
                                    f'in {branch}.'
                                )
                            })

                        subtotal = product.price * cart_item.quantity

                        branch_total += subtotal

                        validated_items.append({
                            'product': product,
                            'inventory': inventory,
                            'quantity': cart_item.quantity,
                        })

                    # Create branch order.
                    order = Order.objects.using(database).create(
                        customer_id=customer.id,
                        checkout_reference=checkout_reference,
                        total_amount=branch_total,
                        status='PENDING',
                        delivery_address=delivery_address
                    )

                    # Create order items and deduct stock.
                    for entry in validated_items:

                        product = entry['product']
                        inventory = entry['inventory']
                        quantity = entry['quantity']

                        OrderItem.objects.using(database).create(
                            order_id=order.id,
                            product_id=product.id,
                            quantity=quantity,
                            unit_price=product.price
                        )

                        Inventory.objects.using(database).filter(
                            id=inventory.id
                        ).update(
                            quantity=F('quantity') - quantity
                        )

                # This branch transaction has committed.
                created_orders.append((database, order.id))

                checkout_total += branch_total

            # Update shared checkout total.
            Checkout.objects.using('default').filter(
                reference=checkout_reference
            ).update(
                total_amount=checkout_total
            )

            # Prepare response before clearing the cart.
            orders = get_checkout_orders(checkout_reference)

            # Remove purchased items from the shared cart.
            CartItem.objects.using('default').filter(
                cart_id=cart.id
            ).delete()

            return Response({
                'message': 'Your order has been placed successfully.',
                'checkout': CheckoutSerializer(checkout).data,
                'checkout_reference': str(checkout_reference),
                'total_amount': str(checkout_total),
                'delivery_address': delivery_address,
                'orders': orders,
            }, status=status.HTTP_201_CREATED)

        except Exception as error:

            # Restore previously committed branch orders.
            compensation_errors = []

            for database, order_id in reversed(created_orders):

                try:
                    restore_branch_order_stock(
                        database,
                        order_id
                    )

                except Exception:
                    compensation_errors.append(database)

            # Delete the checkout record only when compensation succeeds.
            if not compensation_errors:

                Checkout.objects.using('default').filter(
                    reference=checkout_reference
                ).delete()

            if isinstance(error, ValidationError):
                raise error

            raise ValidationError({
                'checkout': (
                    'Checkout could not be completed. '
                    'Please try again.'
                ),
                'recovery_required': bool(compensation_errors),
            })


# =====================================================
# 9. CUSTOMER ORDER HISTORY
#
# GET /api/auth/orders/
# =====================================================

class OrderHistoryView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        checkouts = Checkout.objects.using('default').filter(
            user_id=request.user.id
        ).order_by('-created_at')

        result = []

        for checkout in checkouts:

            orders = get_checkout_orders(
                checkout.reference
            )

            result.append({
                'checkout_reference': str(checkout.reference),
                'total_amount': str(checkout.total_amount),
                'delivery_address': checkout.delivery_address,
                'created_at': checkout.created_at,
                'orders': orders,
            })

        return Response({
            'total_checkouts': len(result),
            'checkouts': result,
        })


# =====================================================
# 10. CUSTOMER ORDER DETAILS
#
# GET /api/auth/orders/<checkout_reference>/
# =====================================================

class OrderDetailView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, checkout_reference):

        checkout = Checkout.objects.using('default').filter(
            reference=checkout_reference,
            user_id=request.user.id
        ).first()

        if checkout is None:

            return Response(
                {'error': 'Order not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        orders = get_checkout_orders(
            checkout.reference
        )

        return Response({
            'checkout_reference': str(checkout.reference),
            'total_amount': str(checkout.total_amount),
            'delivery_address': checkout.delivery_address,
            'created_at': checkout.created_at,
            'orders': orders,
        })


# =====================================================
# END OF VIEWS
# =====================================================
