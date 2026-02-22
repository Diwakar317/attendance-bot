import axios from "axios";

const API = axios.create({
  baseURL: "http://127.0.0.1:8000"
});

API.interceptors.request.use(config => {

  const token = localStorage.getItem("token");

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;

});
API.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.reload(); // force login screen
    }
    return Promise.reject(error);
  }
);

export default API;
