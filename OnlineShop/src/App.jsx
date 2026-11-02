
import { useEffect, useState } from "react";

const API_URL = "http://127.0.0.1:8000/api/auth";

// =====================================================
// API HELPER
// =====================================================

async function apiRequest(endpoint, options = {}, authenticated = false) {
  const token = localStorage.getItem("access_token");

  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (authenticated && token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // Refresh expired access token
  if (response.status === 401 && authenticated) {
    const refreshToken = localStorage.getItem("refresh_token");

    if (refreshToken) {
      const refreshResponse = await fetch(
        `${API_URL}/token/refresh/`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh: refreshToken }),
        }
      );

      if (refreshResponse.ok) {
        const refreshData = await refreshResponse.json();

        localStorage.setItem("access_token", refreshData.access);

        headers.Authorization = `Bearer ${refreshData.access}`;

        response = await fetch(`${API_URL}${endpoint}`, {
          ...options,
          headers,
        });
      } else {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
      }
    }
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error = Object.entries(data)
      .map(([key, value]) => {
        const message = Array.isArray(value)
          ? value.join(", ")
          : typeof value === "object"
            ? JSON.stringify(value)
            : value;

        return `${key}: ${message}`;
      })
      .join(" | ");

    throw new Error(error || `Request failed (${response.status})`);
  }

  return data;
}

// =====================================================
// MAIN APPLICATION
// =====================================================

function App() {
  const [page, setPage] = useState(
    localStorage.getItem("access_token") ? "home" : "login"
  );

  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("error");

  const [customer, setCustomer] = useState(null);
  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState(null);
  const [orders, setOrders] = useState([]);

  const [branch, setBranch] = useState("dar");
  const [search, setSearch] = useState("");
  const [deliveryAddress, setDeliveryAddress] = useState("");

  const [loginData, setLoginData] = useState({
    username: "",
    password: "",
  });

  const [registerData, setRegisterData] = useState({
    username: "",
    email: "",
    phone: "",
    address: "",
    password: "",
  });

  const [showPassword, setShowPassword] = useState(false);

  // ===================================================
  // NOTIFICATIONS
  // ===================================================

  const notify = (text, type = "error") => {
    setMessage(text);
    setMessageType(type);
  };

  // ===================================================
  // LOGIN
  // ===================================================

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");

    try {
      const data = await apiRequest("/login/", {
        method: "POST",
        body: JSON.stringify(loginData),
      });

      localStorage.setItem("access_token", data.access);
      localStorage.setItem("refresh_token", data.refresh);

      setPage("home");
      notify("Login successful!", "success");

    } catch (error) {
      notify(error.message);
    } finally {
      setLoading(false);
    }
  };

  // ===================================================
  // REGISTRATION
  // ===================================================

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");

    try {
      await apiRequest("/register/", {
        method: "POST",
        body: JSON.stringify(registerData),
      });

      setRegisterData({
        username: "",
        email: "",
        phone: "",
        address: "",
        password: "",
      });

      setLoginData({
        username: registerData.username,
        password: "",
      });

      setPage("login");
      notify("Account created successfully. Please login.", "success");

    } catch (error) {
      notify(error.message);
    } finally {
      setLoading(false);
    }
  };

  // ===================================================
  // LOAD CUSTOMER PROFILE
  // ===================================================

  const loadProfile = async () => {
    const data = await apiRequest("/profile/", {}, true);
    setCustomer(data);
  };

  // ===================================================
  // LOAD PRODUCTS
  // ===================================================

  const loadProducts = async () => {
    const data = await apiRequest(
      `/products/?branch=${branch}`
    );

    setProducts(Array.isArray(data) ? data : data.results || []);
  };

  // ===================================================
  // LOAD CART
  // ===================================================

  const loadCart = async () => {
    const data = await apiRequest("/cart/", {}, true);
    setCart(data);
  };

  // ===================================================
  // LOAD ORDERS
  // ===================================================

  const loadOrders = async () => {
  try {
    const data = await apiRequest("/orders/", {}, true);

    // API returns checkouts containing their branch orders
    const checkoutList = data.checkouts || [];

    const formattedOrders = checkoutList.flatMap((checkout) =>
      (checkout.orders || []).map((order) => ({
        ...order,

        // Shared checkout information
        checkout_reference: checkout.checkout_reference,
        checkout_total: checkout.total_amount,
        checkout_delivery_address: checkout.delivery_address,
        checkout_created_at: checkout.created_at,

        // Branch order information
        branch: order.branch,
        items: order.items || [],
      }))
    );

    setOrders(formattedOrders);

  } catch (error) {
    console.error("Failed to load orders:", error);
    setOrders([]);
  }
};

  // ===================================================
  // INITIAL CUSTOMER DATA
  // ===================================================

  useEffect(() => {
    if (page === "home" && localStorage.getItem("access_token")) {
      const loadDashboard = async () => {
        try {
          await Promise.all([
            loadProfile(),
            loadProducts(),
            loadCart(),
          ]);
        } catch (error) {
          notify(error.message);
        }
      };

      loadDashboard();
    }
  }, [page]);

  // Reload products when branch changes
  useEffect(() => {
    if (page === "home") {
      loadProducts().catch((error) => notify(error.message));
    }
  }, [branch]);

  // ===================================================
  // ADD TO CART
  // ===================================================

  const addToCart = async (productId) => {
    setLoading(true);

    try {
      await apiRequest(
        "/cart/add/",
        {
          method: "POST",
          body: JSON.stringify({
            branch,
            product_id: productId,
            quantity: 1,
          }),
        },
        true
      );

      await loadCart();
      notify("Product added to cart!", "success");

    } catch (error) {
      notify(error.message);
    } finally {
      setLoading(false);
    }
  };

  // ===================================================
  // UPDATE CART QUANTITY
  // ===================================================

  const updateCartItem = async (itemId, quantity) => {
    if (quantity < 1) return;

    try {
      await apiRequest(
        `/cart/items/${itemId}/`,
        {
          method: "PATCH",
          body: JSON.stringify({ quantity }),
        },
        true
      );

      await loadCart();
      notify("Cart updated.", "success");

    } catch (error) {
      notify(error.message);
    }
  };

  // ===================================================
  // REMOVE CART ITEM
  // ===================================================

  const removeCartItem = async (itemId) => {
    try {
      await apiRequest(
        `/cart/items/${itemId}/`,
        { method: "DELETE" },
        true
      );

      await loadCart();
      notify("Product removed from cart.", "success");

    } catch (error) {
      notify(error.message);
    }
  };

  // ===================================================
  // CHECKOUT
  // ===================================================

  const handleCheckout = async () => {
    if (!deliveryAddress.trim()) {
      notify("Please enter your delivery address.");
      return;
    }

    setLoading(true);

    try {
      await apiRequest(
        "/orders/checkout/",
        {
          method: "POST",
          body: JSON.stringify({
            delivery_address: deliveryAddress,
          }),
        },
        true
      );

      await Promise.all([loadCart(), loadOrders()]);

      setDeliveryAddress("");
      setPage("orders");

      notify("Checkout completed successfully!", "success");

    } catch (error) {
      notify(error.message);
    } finally {
      setLoading(false);
    }
  };

  // ===================================================
  // LOGOUT
  // ===================================================

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");

    setCustomer(null);
    setProducts([]);
    setCart(null);
    setOrders([]);

    setPage("login");
    notify("You have logged out.", "success");
  };

  // ===================================================
  // SWITCH LOGIN / REGISTER
  // ===================================================

  const switchPage = (selectedPage) => {
    setPage(selectedPage);
    setMessage("");
  };

  // ===================================================
  // FORM INPUT HANDLERS
  // ===================================================

  const handleLoginChange = (e) => {
    setLoginData({
      ...loginData,
      [e.target.name]: e.target.value,
    });
  };

  const handleRegisterChange = (e) => {
    setRegisterData({
      ...registerData,
      [e.target.name]: e.target.value,
    });
  };

  // ===================================================
  // FILTER PRODUCTS
  // ===================================================

  const filteredProducts = products.filter((product) =>
    product.name?.toLowerCase().includes(search.toLowerCase())
  );

  const cartItems = cart?.items || [];

  // ===================================================
  // AUTHENTICATION PAGE
  // ===================================================

  if (page === "login" || page === "register") {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center p-4">

        <div className="w-full max-w-5xl bg-white rounded-3xl shadow-2xl overflow-hidden grid md:grid-cols-2">

          <div className="hidden md:flex flex-col justify-between bg-slate-900 text-white p-12">

            <div>
              <h1 className="text-3xl font-bold">
                Shop<span className="text-orange-400">Hub.</span>
              </h1>

              <p className="text-slate-300 mt-3">
                One account. Two branches. One shopping experience.
              </p>
            </div>

            <div>
              <div className="text-7xl mb-6">🛍️</div>

              <h2 className="text-4xl font-bold leading-snug">
                Shop smarter.
                <br />
                Shop anywhere.
              </h2>

              <p className="text-slate-300 mt-4">
                Explore products from Dar es Salaam and Zanzibar.
              </p>
            </div>

            <p className="text-sm text-slate-400">
              Distributed Online Shopping System
            </p>

          </div>

          <div className="p-7 sm:p-10 lg:p-12">

            <div className="md:hidden text-2xl font-bold mb-8">
              Shop<span className="text-orange-500">Hub.</span>
            </div>

            <div className="flex gap-2 bg-slate-100 p-1 rounded-xl mb-8">

              <button
                onClick={() => switchPage("login")}
                className={`flex-1 py-3 rounded-lg font-semibold ${
                  page === "login"
                    ? "bg-white shadow text-slate-900"
                    : "text-slate-500"
                }`}
              >
                Login
              </button>

              <button
                onClick={() => switchPage("register")}
                className={`flex-1 py-3 rounded-lg font-semibold ${
                  page === "register"
                    ? "bg-white shadow text-slate-900"
                    : "text-slate-500"
                }`}
              >
                Register
              </button>

            </div>

            <h2 className="text-3xl font-bold text-slate-900">
              {page === "login" ? "Welcome back!" : "Create account"}
            </h2>

            <p className="text-slate-500 mt-2 mb-6">
              {page === "login"
                ? "Login to continue shopping."
                : "Create your customer account."}
            </p>

            {message && (
              <div className={`p-3 mb-5 rounded-lg text-sm ${
                messageType === "success"
                  ? "bg-green-100 text-green-700"
                  : "bg-red-100 text-red-700"
              }`}>
                {message}
              </div>
            )}

            {page === "login" ? (

              <form onSubmit={handleLogin} className="space-y-5">

                <div>
                  <label className="block mb-2 font-semibold text-sm">
                    Username
                  </label>

                  <input
                    name="username"
                    value={loginData.username}
                    onChange={handleLoginChange}
                    placeholder="Enter username"
                    required
                    className="w-full border rounded-xl px-4 py-3 outline-none focus:ring-2 focus:ring-orange-400"
                  />
                </div>

                <div>
                  <label className="block mb-2 font-semibold text-sm">
                    Password
                  </label>

                  <div className="relative">
                    <input
                      type={showPassword ? "text" : "password"}
                      name="password"
                      value={loginData.password}
                      onChange={handleLoginChange}
                      placeholder="Enter password"
                      required
                      className="w-full border rounded-xl px-4 py-3 pr-16 outline-none focus:ring-2 focus:ring-orange-400"
                    />

                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-4 top-3 text-orange-600 text-sm"
                    >
                      {showPassword ? "Hide" : "Show"}
                    </button>
                  </div>
                </div>

                <button
                  disabled={loading}
                  className="w-full bg-orange-500 hover:bg-orange-600 disabled:opacity-60 text-white py-3 rounded-xl font-bold"
                >
                  {loading ? "Please wait..." : "Login"}
                </button>

                <p className="text-center text-sm text-slate-500">
                  Don't have an account?{" "}
                  <button
                    type="button"
                    onClick={() => switchPage("register")}
                    className="text-orange-600 font-bold"
                  >
                    Register
                  </button>
                </p>

              </form>

            ) : (

              <form onSubmit={handleRegister} className="space-y-4">

                {[
                  ["username", "Username", "Enter username", "text"],
                  ["email", "Email Address", "Enter email", "email"],
                  ["phone", "Phone Number", "Enter phone number", "tel"],
                  ["address", "Address", "Enter your address", "text"],
                  ["password", "Password", "Create password", "password"],
                ].map(([name, label, placeholder, type]) => (

                  <div key={name}>
                    <label className="block mb-2 font-semibold text-sm">
                      {label}
                    </label>

                    <input
                      type={type}
                      name={name}
                      value={registerData[name]}
                      onChange={handleRegisterChange}
                      placeholder={placeholder}
                      required
                      minLength={name === "password" ? 8 : undefined}
                      className="w-full border rounded-xl px-4 py-3 outline-none focus:ring-2 focus:ring-orange-400"
                    />
                  </div>

                ))}

                <button
                  disabled={loading}
                  className="w-full bg-orange-500 hover:bg-orange-600 disabled:opacity-60 text-white py-3 rounded-xl font-bold"
                >
                  {loading ? "Creating account..." : "Create Account"}
                </button>

                <p className="text-center text-sm text-slate-500">
                  Already have an account?{" "}
                  <button
                    type="button"
                    onClick={() => switchPage("login")}
                    className="text-orange-600 font-bold"
                  >
                    Login
                  </button>
                </p>

              </form>

            )}

          </div>
        </div>
      </div>
    );
  }

  // ===================================================
  // CUSTOMER SHOPPING APPLICATION
  // ===================================================

  return (
    <div className="min-h-screen bg-slate-100">

      {/* NAVIGATION */}
      <nav className="bg-slate-900 text-white px-5 py-4">

        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">

          <h1 className="text-2xl font-bold">
            Shop<span className="text-orange-400">Hub.</span>
          </h1>

          <div className="flex flex-wrap items-center gap-5 text-sm">

            <button onClick={() => setPage("home")}>
              Products
            </button>

            <button onClick={() => {
              setPage("cart");
              loadCart();
            }}>
              Cart ({cart?.total_items || 0})
            </button>

            <button onClick={() => {
              setPage("orders");
              loadOrders();
            }}>
              My Orders
            </button>

            <button onClick={() => setPage("profile")}>
              My Profile
            </button>

            <button
              onClick={handleLogout}
              className="bg-red-500 px-4 py-2 rounded-lg"
            >
              Logout
            </button>

          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto p-5">

        {message && (
          <div className={`mb-5 p-3 rounded-lg text-sm ${
            messageType === "success"
              ? "bg-green-100 text-green-700"
              : "bg-red-100 text-red-700"
          }`}>
            {message}
            <button
              onClick={() => setMessage("")}
              className="float-right font-bold"
            >
              ×
            </button>
          </div>
        )}

        {/* PRODUCTS */}
        {page === "home" && (
          <>

            <div className="bg-white rounded-2xl p-7 mb-7 shadow-sm">
              <h2 className="text-3xl font-bold text-slate-900">
                Welcome, {customer?.username || "Customer"}!
              </h2>

              <p className="text-slate-500 mt-2">
                Discover products from our shopping branches.
              </p>
            </div>

            <div className="flex flex-wrap justify-between gap-4 mb-6">

              <div className="flex gap-2">
                <button
                  onClick={() => setBranch("dar")}
                  className={`px-5 py-3 rounded-xl font-semibold ${
                    branch === "dar"
                      ? "bg-orange-500 text-white"
                      : "bg-white text-slate-700"
                  }`}
                >
                  Dar es Salaam
                </button>

                <button
                  onClick={() => setBranch("zanzibar")}
                  className={`px-5 py-3 rounded-xl font-semibold ${
                    branch === "zanzibar"
                      ? "bg-orange-500 text-white"
                      : "bg-white text-slate-700"
                  }`}
                >
                  Zanzibar
                </button>
              </div>

              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search products..."
                className="border rounded-xl px-4 py-3 bg-white"
              />

            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">

              {filteredProducts.map((product) => (

                <div
                  key={product.id}
                  className="bg-white rounded-2xl shadow-sm overflow-hidden"
                >

                  {product.image ? (
                    <img
                      src={product.image}
                      alt={product.name}
                      className="w-full h-48 object-cover"
                    />
                  ) : (
                    <div className="h-48 bg-slate-200 flex items-center justify-center text-5xl">
                      🛍️
                    </div>
                  )}

                  <div className="p-5">

                    <h3 className="font-bold text-lg">
                      {product.name}
                    </h3>

                    <p className="text-slate-500 text-sm mt-2 line-clamp-2">
                      {product.description}
                    </p>

                    <p className="text-orange-600 text-xl font-bold mt-4">
                      TZS {Number(product.price).toLocaleString()}
                    </p>

                    <p className="text-sm text-slate-500 mt-2">
                      Stock: {product.stock_quantity ?? "Check availability"}
                    </p>

                    <button
                      onClick={() => addToCart(product.id)}
                      disabled={loading || product.is_available === false}
                      className="w-full mt-4 bg-slate-900 hover:bg-orange-500 disabled:opacity-50 text-white py-3 rounded-xl font-semibold"
                    >
                      Add to Cart
                    </button>

                  </div>
                </div>

              ))}

            </div>

            {filteredProducts.length === 0 && (
              <p className="text-center text-slate-500 py-12">
                No products found in this branch.
              </p>
            )}

          </>
        )}

        {/* SHOPPING CART */}
        {page === "cart" && (
          <div className="bg-white rounded-2xl p-6 shadow-sm">

            <h2 className="text-2xl font-bold mb-6">
              My Shopping Cart
            </h2>

            {cartItems.length === 0 ? (
              <p className="text-slate-500">
                Your cart is empty.
              </p>
            ) : (

              <div className="space-y-5">

                {cartItems.map((item) => (

                  <div
                    key={item.id}
                    className="border-b pb-5 flex flex-wrap justify-between gap-4"
                  >

                    <div>
                      <h3 className="font-bold">
                        {item.product_name}
                      </h3>

                      <p className="text-sm text-slate-500">
                        Branch: {item.branch}
                      </p>

                      <p className="text-orange-600 font-bold">
                        TZS {Number(item.price).toLocaleString()}
                      </p>
                    </div>

                    <div className="flex items-center gap-3">

                      <button
                        onClick={() =>
                          updateCartItem(item.id, item.quantity - 1)
                        }
                        className="bg-slate-200 px-3 py-2 rounded"
                      >
                        -
                      </button>

                      <span>{item.quantity}</span>

                      <button
                        onClick={() =>
                          updateCartItem(item.id, item.quantity + 1)
                        }
                        className="bg-slate-200 px-3 py-2 rounded"
                      >
                        +
                      </button>

                      <button
                        onClick={() => removeCartItem(item.id)}
                        className="text-red-600 font-semibold ml-2"
                      >
                        Remove
                      </button>

                    </div>

                    <p className="font-bold">
                      TZS {Number(item.line_total || 0).toLocaleString()}
                    </p>

                  </div>

                ))}

                <div className="pt-4">
                  <h3 className="text-xl font-bold">
                    Total: TZS{" "}
                    {Number(cart?.total_amount || 0).toLocaleString()}
                  </h3>

                  <div className="mt-5">
                    <label className="block font-semibold mb-2">
                      Delivery Address
                    </label>

                    <textarea
                      value={deliveryAddress}
                      onChange={(e) =>
                        setDeliveryAddress(e.target.value)
                      }
                      placeholder="Enter delivery address"
                      className="w-full border rounded-xl p-3"
                      rows="3"
                    />
                  </div>

                  <button
                    onClick={handleCheckout}
                    disabled={loading}
                    className="mt-5 bg-orange-500 hover:bg-orange-600 text-white px-8 py-3 rounded-xl font-bold"
                  >
                    {loading ? "Processing..." : "Place Order"}
                  </button>

                </div>

              </div>
            )}

          </div>
        )}

        {/* ORDER HISTORY */}
        {page === "orders" && (
          <div className="bg-white rounded-2xl p-6 shadow-sm">

            <h2 className="text-2xl font-bold mb-6">
              My Orders
            </h2>

            {orders.length === 0 ? (
              <p className="text-slate-500">
                You have no orders yet.
              </p>
            ) : (

              <div className="space-y-4">

                {orders.map((order, index) => (

                  <div
                    key={order.reference || order.id || index}
                    className="border rounded-xl p-5"
                  >

                    <p className="font-bold break-all">
                      Checkout: {order.reference || order.checkout_reference}
                    </p>

                    <p className="text-slate-500 mt-2">
                      Total: TZS{" "}
                      {Number(order.total_amount || 0).toLocaleString()}
                    </p>

                    <p className="mt-2">
                      Status:{" "}
                      <span className="font-semibold text-orange-600">
                        {order.status || "Processing"}
                      </span>
                    </p>

                    {order.orders?.map((branchOrder) => (
                      <div
                        key={branchOrder.id}
                        className="mt-4 border-t pt-3"
                      >
                        <p className="font-semibold">
                          {branchOrder.branch || "Branch order"}
                        </p>
                        <p>
                          Status: {branchOrder.status}
                        </p>
                      </div>
                    ))}

                  </div>

                ))}

              </div>

            )}

          </div>
        )}

        {/* CUSTOMER PROFILE */}
        {page === "profile" && (
          <div className="bg-white rounded-2xl p-7 shadow-sm max-w-2xl">

            <h2 className="text-2xl font-bold mb-6">
              My Profile
            </h2>

            {customer ? (
              <div className="space-y-4">

                <div>
                  <p className="text-slate-500 text-sm">Username</p>
                  <p className="font-semibold">{customer.username}</p>
                </div>

                <div>
                  <p className="text-slate-500 text-sm">Email</p>
                  <p className="font-semibold">{customer.email}</p>
                </div>

                <div>
                  <p className="text-slate-500 text-sm">Phone</p>
                  <p className="font-semibold">
                    {customer.phone || "Not provided"}
                  </p>
                </div>

                <div>
                  <p className="text-slate-500 text-sm">Address</p>
                  <p className="font-semibold">
                    {customer.address || "Not provided"}
                  </p>
                </div>

              </div>
            ) : (
              <p>Loading profile...</p>
            )}

          </div>
        )}

      </main>

      <footer className="text-center text-slate-500 text-sm py-8">
        Distributed Online Shopping System
      </footer>

    </div>
  );
}

export default App;
