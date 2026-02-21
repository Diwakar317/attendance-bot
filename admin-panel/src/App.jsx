import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useState } from "react";
import Sidebar from "./components/Sidebar";

import Dashboard from "./pages/Dashboard";
import Users from "./pages/Users";
import Attendance from "./pages/Attendance";
import CreateUser from "./pages/CreateUser";
import Login from "./pages/Login";

function App() {
  const [token, setToken] = useState(
    localStorage.getItem("token")
  );

  if (!token) {
    return <Login setToken={setToken} />;
  }

  return (

    <BrowserRouter>

      <Sidebar />

      <div style={{ marginLeft: 240, padding: 20 }}>

        <Routes>

          <Route path="/" element={<Dashboard />} />

          <Route path="/users" element={<Users />} />

          <Route path="/attendance" element={<Attendance />} />

          <Route path="/create-user" element={<CreateUser />} />

        </Routes>

      </div>

    </BrowserRouter>

  );
}

export default App;
