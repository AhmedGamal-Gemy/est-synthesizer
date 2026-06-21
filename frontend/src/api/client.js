import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL + '/api',
  timeout: 10000, // 10 seconds timeout for performance
  headers: {
    'Content-Type': 'application/json',
  },
});

// Security: Intercept requests to attach auth tokens if you have them
client.interceptors.request.use(
  (config) => {
    // Example: const token = localStorage.getItem('token');
    // if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error) => Promise.reject(error)
);

// UX: Intercept responses to handle global errors
client.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle global errors (e.g., 401 Unauthorized, 500 Server errors)
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export default client;