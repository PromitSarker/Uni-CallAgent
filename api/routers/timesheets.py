from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import date, time
from agent.db import get_connection

router = APIRouter(prefix="/timesheets", tags=["timesheets"])

class TimesheetCreate(BaseModel):
    locum_email: EmailStr
    shift_date: date
    scheduled_start_time: time
    scheduled_end_time: time
    actual_start_time: time
    actual_end_time: time
    scheduled_break_minutes: int
    actual_break_minutes: int
    notes: Optional[str] = None

class TimesheetResponse(TimesheetCreate):
    id: int
    status: str
    
@router.post("")
def create_timesheet(timesheet: TimesheetCreate):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO timesheets (
                        locum_email, shift_date, 
                        scheduled_start_time, scheduled_end_time, 
                        actual_start_time, actual_end_time, 
                        scheduled_break_minutes, actual_break_minutes, 
                        notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, status
                    """,
                    (
                        timesheet.locum_email, timesheet.shift_date,
                        timesheet.scheduled_start_time, timesheet.scheduled_end_time,
                        timesheet.actual_start_time, timesheet.actual_end_time,
                        timesheet.scheduled_break_minutes, timesheet.actual_break_minutes,
                        timesheet.notes
                    )
                )
                result = cur.fetchone()
            conn.commit()
            return {"status": "success", "id": result["id"], "timesheet_status": result["status"]}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{locum_email}")
def get_timesheets(locum_email: str):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM timesheets WHERE locum_email = %s ORDER BY shift_date DESC",
                    (locum_email,)
                )
                rows = cur.fetchall()
                # RealDictCursor makes rows dictionary-like
                return {"status": "success", "data": rows}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
