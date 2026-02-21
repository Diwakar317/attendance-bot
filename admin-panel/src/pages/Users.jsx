import { useEffect, useState } from "react";
import API from "../api";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Button,
  Avatar,
  Box
} from "@mui/material";


export default function Users() {

  const [users, setUsers] = useState([]);
  const [faces, setFaces] = useState({});


  useEffect(() => {
    loadUsers();
  }, []);


  useEffect(() => {
    users.forEach(u => loadFaces(u.id));
  }, [users]);


  function loadUsers() {
    API.get("/users")
      .then(res => setUsers(res.data));
  }


  function loadFaces(userId) {

    API.get(`/users/${userId}/faces`)
      .then(res => {

        const faceList = res.data.faces || [];

        const urls = faceList.map(
  path => `http://127.0.0.1:8000${path}`
);


        setFaces(prev => ({
          ...prev,
          [userId]: urls
        }));

      })
      .catch(() => {

        setFaces(prev => ({
          ...prev,
          [userId]: []
        }));

      });

  }


  function deleteUser(id) {

    if (!confirm("Delete this user?")) return;

    API.delete(`/users/${id}`)
      .then(() => {
        loadUsers();
      });

  }


  function uploadFaces(userId, files) {

    if (files.length === 0) return;

    const formData = new FormData();

    Array.from(files).forEach(file =>
      formData.append("faces", file)
    );

    API.post(`/users/${userId}/face`, formData)
      .then(() => {

        alert("Faces updated");

        loadUsers();

      })
      .catch(err =>
        alert(err.response?.data?.detail)
      );

  }


  function handleFileChange(userId, e) {

    const files = e.target.files;

    if (!files) return;

    if (files.length > 3) {
      alert("Maximum 3 faces allowed");
      return;
    }

    uploadFaces(userId, files);

  }


  return (

    <Table>

      <TableHead>

        <TableRow>

          <TableCell>Faces</TableCell>
          <TableCell>Name</TableCell>
          <TableCell>Phone</TableCell>
          <TableCell>Update Faces</TableCell>
          <TableCell>Delete User</TableCell>

        </TableRow>

      </TableHead>


      <TableBody>

        {users.map(u => (

          <TableRow key={u.id}>

            {/* Faces preview */}
            <TableCell>

              <Box sx={{ display: "flex", gap: 1 }}>

                {(faces[u.id] || []).map((src, i) => (

                  <Avatar
                    key={i}
                    src={src}
                    sx={{ width: 50, height: 50 }}
                  />

                ))}

              </Box>

            </TableCell>


            {/* Name */}
            <TableCell>
              {u.name}
            </TableCell>


            {/* Phone */}
            <TableCell>
              {u.phone}
            </TableCell>


            {/* Upload faces */}
            <TableCell>

              <Button
                variant="contained"
                component="label"
              >
                Upload

                <input
                  hidden
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={(e) =>
                    handleFileChange(u.id, e)
                  }
                />

              </Button>

            </TableCell>


            {/* Delete user */}
            <TableCell>

              <Button
                variant="contained"
                color="error"
                onClick={() =>
                  deleteUser(u.id)
                }
              >
                Delete
              </Button>

            </TableCell>


          </TableRow>

        ))}

      </TableBody>

    </Table>

  );
}
