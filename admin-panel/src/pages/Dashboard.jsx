import { useEffect, useState } from "react";
import API from "../api";
import { Card, CardContent, Typography, Grid } from "@mui/material";

export default function Dashboard() {

  const [data, setData] = useState({});

  useEffect(() => {
    API.get("/dashboard")
      .then(res => setData(res.data));
  }, []);

  return (

    <Grid container spacing={3}>

      <Grid item xs={4}>
        <Card>
          <CardContent>
            <Typography variant="h5">
              Total Users
            </Typography>

            <Typography variant="h4">
              {data.total_users}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={4}>
        <Card>
          <CardContent>
            <Typography variant="h5">
              Total Attendance
            </Typography>

            <Typography variant="h4">
              {data.total_attendance}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={4}>
        <Card>
          <CardContent>
            <Typography variant="h5">
              Today Attendance
            </Typography>

            <Typography variant="h4">
              {data.today_attendance}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

    </Grid>

  );
}
