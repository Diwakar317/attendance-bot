import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useState } from "react";

import Sidebar from "./components/Sidebar";
import ProtectedRoute from "./components/ProtectedRoute";

import Dashboard from "./pages/Dashboard";
import Users from "./pages/Users";
import Attendance from "./pages/Attendance";
import CreateUser from "./pages/CreateUser";
import Login from "./pages/Login";

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"));

  return (
    <BrowserRouter>
      {token && <Sidebar setToken={setToken} />}

      <div style={{ marginLeft: token ? 240 : 0, padding: 20 }}>
        <Routes>

          {/* Public Route */}
          <Route
            path="/"
            element={
              token ? <Navigate to="/dashboard" replace /> : <Login setToken={setToken} />
            }
          />

          {/* Protected Routes */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute token={token}>
                <Dashboard />
              </ProtectedRoute>
            }
          />

          <Route
            path="/users"
            element={
              <ProtectedRoute token={token}>
                <Users />
              </ProtectedRoute>
            }
          />

          <Route
            path="/attendance"
            element={
              <ProtectedRoute token={token}>
                <Attendance />
              </ProtectedRoute>
            }
          />

          <Route
            path="/create-user"
            element={
              <ProtectedRoute token={token}>
                <CreateUser />
              </ProtectedRoute>
            }
          />

          {/* Catch all */}
          <Route
            path="*"
            element={<Navigate to={token ? "/dashboard" : "/"} replace />}
          />

        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;