import { useState } from "react";
import { useNavigate } from "react-router-dom";   // 🔥 add this
import API from "../api";
import { TextField, Button, Box, Typography } from "@mui/material";

export default function Login({ setToken }) {

  const navigate = useNavigate();   // 🔥 add this

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  function login() {

    API.post("/login", {
      username,
      password
    })
    .then(res => {

      localStorage.setItem(
        "token",
        res.data.access_token
      );

      setToken(res.data.access_token);

      navigate("/", { replace: true });   // 🔥 force dashboard

    })
    .catch(() => alert("Invalid login"));

  }

  return (

    <Box sx={{ width: 300, margin: "auto", mt: 10 }}>

      <Typography variant="h5">
        Admin Login
      </Typography>

      <TextField
        fullWidth
        label="Username"
        margin="normal"
        onChange={e => setUsername(e.target.value)}
      />

      <TextField
        fullWidth
        type="password"
        label="Password"
        margin="normal"
        onChange={e => setPassword(e.target.value)}
      />

      <Button
        fullWidth
        variant="contained"
        onClick={login}
      >
        Login
      </Button>

    </Box>

  );
}