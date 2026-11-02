
class DatabaseRouter:

    # Django shared applications
    shared_apps = {
        'auth',
        'contenttypes',
        'admin',
        'sessions',
    }

    # Branch databases
    branch_databases = {
        'dar',
        'zanzibar',
    }

    # Models stored ONLY in shared_customer_db
    shared_shop_models = {
        'customer',
        'cart',
        'cartitem',
        'checkout',
    }

    # =================================================
    # DATABASE READ ROUTING
    # =================================================

    def db_for_read(self, model, **hints):

        app = model._meta.app_label
        model_name = model._meta.model_name

        if app == 'shop':

            # Shared customer and checkout data
            if model_name in self.shared_shop_models:
                return 'default'

            # Branch-specific models
            return hints.get('branch', 'dar')

        if app in self.shared_apps:
            return 'default'

        return None

    # =================================================
    # DATABASE WRITE ROUTING
    # =================================================

    def db_for_write(self, model, **hints):

        return self.db_for_read(model, **hints)

    # =================================================
    # DATABASE RELATIONSHIP
    # =================================================

    def allow_relation(self, obj1, obj2, **hints):

        db1 = obj1._state.db
        db2 = obj2._state.db

        return db1 == db2

    # =================================================
    # DATABASE MIGRATION ROUTING
    # =================================================

    def allow_migrate(
        self,
        db,
        app_label,
        model_name=None,
        **hints
    ):

        # Shared shop models
        if app_label == 'shop':

            if model_name in self.shared_shop_models:
                return db == 'default'

            # Branch-specific shop models
            return db in self.branch_databases

        # Django authentication and administration
        if app_label in self.shared_apps:
            return db == 'default'

        # Other installed Django applications
        return db == 'default'
