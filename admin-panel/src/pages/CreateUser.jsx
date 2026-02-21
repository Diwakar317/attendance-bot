import { useState } from "react";
import API from "../api";

import {
  TextField,
  Button,
  Box,
  Typography,
  Avatar
} from "@mui/material";


export default function CreateUser() {

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [faces, setFaces] = useState([]);
  const [previews, setPreviews] = useState([]);


  function handleImageChange(e) {

    const files = Array.from(e.target.files);

    if (files.length > 3) {
      alert("Maximum 3 images allowed");
      return;
    }

    setFaces(files);

    const urls = files.map(file =>
      URL.createObjectURL(file)
    );

    setPreviews(urls);
  }


  function handleSubmit() {

    if (!name || !phone || faces.length === 0) {
      alert("Fill all fields and upload faces");
      return;
    }

    const formData = new FormData();

    formData.append("name", name);
    formData.append("phone", phone);

    faces.forEach(face =>
      formData.append("faces", face)
    );

    API.post("/users", formData)
      .then(() => {

        alert("User created");

        setName("");
        setPhone("");
        setFaces([]);
        setPreviews([]);

      })
      .catch(err =>
        alert(err.response?.data?.detail)
      );

  }


  return (

    <Box sx={{ width: 400 }}>

      <Typography variant="h5">
        Create User
      </Typography>


      <TextField
        fullWidth
        label="Name"
        margin="normal"
        value={name}
        onChange={e => setName(e.target.value)}
      />


      <TextField
        fullWidth
        label="Phone"
        margin="normal"
        value={phone}
        onChange={e => setPhone(e.target.value)}
      />


      <Button
        variant="outlined"
        component="label"
      >
        Upload Faces (max 3)

        <input
          hidden
          type="file"
          accept="image/*"
          multiple
          onChange={handleImageChange}
        />

      </Button>


      <Box sx={{ display: "flex", gap: 1, mt: 2 }}>

        {previews.map((src, i) => (

          <Avatar
            key={i}
            src={src}
            sx={{
              width: 80,
              height: 80
            }}
          />

        ))}

      </Box>


      <Button
        variant="contained"
        fullWidth
        sx={{ mt: 2 }}
        onClick={handleSubmit}
      >
        Create User
      </Button>


    </Box>

  );
}
