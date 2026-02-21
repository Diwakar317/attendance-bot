import { useEffect, useState } from "react";
import API from "../api";
import {
  Table, TableBody, TableCell,
  TableHead, TableRow
} from "@mui/material";

export default function Attendance() {

  const [records, setRecords] = useState([]);

  useEffect(() => {

    API.get("/attendance")
      .then(res => setRecords(res.data));

  }, []);

  return (

    <Table>

      <TableHead>

        <TableRow>

          <TableCell>Name</TableCell>

          <TableCell>Phone</TableCell>

          <TableCell>Check In</TableCell>

          <TableCell>Check Out</TableCell>

        </TableRow>

      </TableHead>

      <TableBody>

        {records.map(r => (

          <TableRow key={r.id}>

            <TableCell>{r.name}</TableCell>

            <TableCell>{r.phone}</TableCell>

            <TableCell>{r.check_in}</TableCell>

            <TableCell>{r.check_out}</TableCell>

          </TableRow>

        ))}

      </TableBody>

    </Table>

  );
}
