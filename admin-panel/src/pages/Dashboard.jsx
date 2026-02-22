import { useEffect, useState } from "react";
import API from "../api";
import {
  Card,
  CardContent,
  Typography,
  Box,
  CircularProgress,
  Divider
} from "@mui/material";
import Grid from "@mui/material/Grid";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid
} from "recharts";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    API.get("/dashboard")
      .then(res => setData(res.data))
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" mt={6}>
        <CircularProgress />
      </Box>
    );
  }

  const { summary, time_metrics, trend } = data;

  return (
    <Box p={3}>
      <Typography variant="h4" gutterBottom>
        Admin Dashboard
      </Typography>

      {/* ================= KPI CARDS ================= */}
      <Grid container spacing={3}>

        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2">Total Users</Typography>
              <Typography variant="h4">
                {summary.total_users}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2">Total Attendance</Typography>
              <Typography variant="h4">
                {summary.total_attendance}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2">Today's Attendance</Typography>
              <Typography variant="h4">
                {summary.today_attendance}
              </Typography>
              <Divider sx={{ my: 1 }} />
              <Typography variant="body2">
                Active Users: {summary.active_users_today}
              </Typography>
              <Typography variant="body2">
                Rate: {summary.attendance_rate_today}%
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2">Weekly / Monthly</Typography>
              <Typography variant="body1">
                Weekly: {time_metrics.weekly_attendance}
              </Typography>
              <Typography variant="body1">
                Monthly: {time_metrics.monthly_attendance}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

      </Grid>

      {/* ================= TREND CHART ================= */}
      <Box mt={6}>
        <Typography variant="h5" gutterBottom>
          Last 7 Days Attendance Trend
        </Typography>

        <Card>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={trend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="attendance"
                  stroke="#1976d2"
                  strokeWidth={3}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}