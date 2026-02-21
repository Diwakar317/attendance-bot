import { Link } from "react-router-dom";
import { Drawer, List, ListItem, ListItemText } from "@mui/material";

export default function Sidebar() {

  return (
    <Drawer variant="permanent">

      <List>

        <ListItem button component={Link} to="/">
          <ListItemText primary="Dashboard" />
        </ListItem>

        <ListItem button component={Link} to="/users">
          <ListItemText primary="Users" />
        </ListItem>

        <ListItem button component={Link} to="/attendance">
          <ListItemText primary="Attendance" />
        </ListItem>
        
        <ListItem button component={Link} to="/create-user">
           <ListItemText primary="Create User" />
        </ListItem>

      </List>

    </Drawer>
  );
}
