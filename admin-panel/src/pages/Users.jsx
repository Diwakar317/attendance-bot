import { useEffect, useState, useRef } from "react";
import API from "../api";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Button,
  Avatar,
  Box,
  Tooltip,
  IconButton
} from "@mui/material";

import EditIcon from "@mui/icons-material/Edit";
import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";


export default function Users() {

  const [users, setUsers] = useState([]);
  const [faces, setFaces] = useState({});
  const faceInputRefs = useRef({});


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


  function handleFaceReplace(userId, faceIndex, e) {

    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("face", file);

    API.put(`/users/${userId}/face/${faceIndex}`, formData)
      .then(() => {
        loadFaces(userId);
      })
      .catch(err =>
        alert(err.response?.data?.detail || "Failed to update face")
      );

    e.target.value = "";
  }


  function handleDeleteFace(userId, faceIndex) {

    if (!confirm(`Delete face ${faceIndex}?`)) return;

    API.delete(`/users/${userId}/face/${faceIndex}`)
      .then(() => {
        loadFaces(userId);
        loadUsers();
      })
      .catch(err =>
        alert(err.response?.data?.detail || "Failed to delete face")
      );
  }


  function handleAddFace(userId, e) {

    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("face", file);

    API.post(`/users/${userId}/face`, formData)
      .then(() => {
        loadFaces(userId);
        loadUsers();
      })
      .catch(err =>
        alert(err.response?.data?.detail || "Failed to add face")
      );

    e.target.value = "";
  }


  function deleteUser(id) {

    if (!confirm("Delete this user?")) return;

    API.delete(`/users/${id}`)
      .then(() => {
        loadUsers();
      });

  }




  return (

    <Table>

      <TableHead>

        <TableRow>

          <TableCell>Faces</TableCell>
          <TableCell>Name</TableCell>
          <TableCell>Phone</TableCell>
          <TableCell>Delete User</TableCell>

        </TableRow>

      </TableHead>


      <TableBody>

        {users.map(u => (

          <TableRow key={u.id}>

            {/* Faces preview — click to replace */}
            <TableCell>

              <Box sx={{ display: "flex", gap: 1 }}>

                {(faces[u.id] || []).map((src, i) => {

                  const faceIndex = i + 1;
                  const refKey = `${u.id}_${faceIndex}`;

                  return (
                    <Tooltip
                      key={i}
                      title={`Click to replace face ${faceIndex}`}
                      arrow
                    >
                      <Box sx={{ position: "relative", cursor: "pointer" }}>

                        <IconButton
                          size="small"
                          sx={{
                            position: "absolute",
                            top: -8,
                            right: -8,
                            bgcolor: "error.main",
                            color: "white",
                            width: 18,
                            height: 18,
                            zIndex: 1,
                            "&:hover": { bgcolor: "error.dark" }
                          }}
                          onClick={() =>
                            handleDeleteFace(u.id, faceIndex)
                          }
                        >
                          <CloseIcon sx={{ fontSize: 12 }} />
                        </IconButton>

                        <Avatar
                          src={`${src}?t=${Date.now()}`}
                          sx={{ width: 50, height: 50 }}
                          onClick={() =>
                            faceInputRefs.current[refKey]?.click()
                          }
                        />

                        <IconButton
                          size="small"
                          sx={{
                            position: "absolute",
                            bottom: -4,
                            right: -4,
                            bgcolor: "white",
                            boxShadow: 1,
                            width: 20,
                            height: 20
                          }}
                          onClick={() =>
                            faceInputRefs.current[refKey]?.click()
                          }
                        >
                          <EditIcon sx={{ fontSize: 12 }} />
                        </IconButton>

                        <input
                          hidden
                          type="file"
                          accept="image/*"
                          ref={el =>
                            (faceInputRefs.current[refKey] = el)
                          }
                          onChange={e =>
                            handleFaceReplace(u.id, faceIndex, e)
                          }
                        />

                      </Box>
                    </Tooltip>
                  );

                })}

                {/* Add face placeholder when < 3 faces */}
                {(faces[u.id] || []).length < 3 && (
                  <Tooltip title="Add new face" arrow>
                    <Box sx={{ position: "relative", cursor: "pointer" }}>

                      <Avatar
                        sx={{
                          width: 50,
                          height: 50,
                          bgcolor: "grey.200",
                          border: "2px dashed",
                          borderColor: "grey.400"
                        }}
                        onClick={() =>
                          faceInputRefs.current[`${u.id}_add`]?.click()
                        }
                      >
                        <AddIcon sx={{ color: "grey.600" }} />
                      </Avatar>

                      <input
                        hidden
                        type="file"
                        accept="image/*"
                        ref={el =>
                          (faceInputRefs.current[`${u.id}_add`] = el)
                        }
                        onChange={e => handleAddFace(u.id, e)}
                      />

                    </Box>
                  </Tooltip>
                )}

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
