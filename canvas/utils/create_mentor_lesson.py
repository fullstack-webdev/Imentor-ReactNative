# -*- coding: iso8859-15 -*-
import os,sys
import re
import pdb
import pprint
import traceback
import psycopg2
from dateutil import tz
from datetime import datetime,timedelta
appdir = os.path.abspath(os.path.dirname(__file__))
projdir = os.path.abspath(os.path.join(appdir,'..'))
projdir2 = os.path.abspath(os.path.join(appdir,'../..'))
if projdir2 not in sys.path:
    sys.path.append(appdir)
    sys.path.append(projdir)
    sys.path.append(projdir2)

from config.project_globals import Base,metadata,DBSession,get_scoped_session

#Import 'app' object from auth as well
from auth import api, app

from flask import  current_app, request, redirect, render_template

import sqlalchemy
from sqlalchemy import (BigInteger, Boolean, Column, Date, DateTime, desc,
    Float, ForeignKey, Index, Integer, Numeric, SmallInteger,
    String, Table, Text, Time, text, DATE, func, UniqueConstraint)
from sqlalchemy.dialects.postgresql.base import INET, TSVECTOR
from sqlalchemy.sql.expression import func, or_, not_, and_
from sqlalchemy.orm import relationship
from legacy_models.member import MemberMember
from legacy_models.utils import UtilsTimezone
from legacy_models.partners import PartnersPartner,PartnersSession
from legacy_models.iuser import (IuserUser,IuserUsertype,IuserPersona,
    IuserPersonaPartner,IuserAssignedusertype,USERTYPE_MAP,ACTIVE_PERSONA_STATUS)
from new_platform.utils.user_details import (get_persona_obj_for_user,
    get_latest_mentee_user_for_mentor, get_latest_mentor_user_for_mentee,
    get_partners_for_user,get_users_for_partners,get_admin_obj_for_user)
from new_platform.utils.roles import Role
from new_platform.utils.user_details import user_timezone
from google_services.gdrive import create_gdoc_copy
from canvas.models import *
from canvas.canvas_scheduling import schedule_fix_lessons
from attendance.models import Attendance

# We prefer this display formats for dates and times, since they are succinct yet still descriptive.
DATETIME_DISPLAY_FORMAT = '%-m/%-d/%y %-I:%M %p'

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Change these!

# Sometimes you create a new unit, sometimes you reuse one.
#unit_id=5  
grade_id=4  # 12th grade
canvas_type=CANVAS_TYPE_OPENING_LESSON
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def make_mentor_curriculum(local_db_session,cur_id,mentee_content_to_attach_to):

    cur = local_db_session.query(Curriculum).filter(
        Curriculum.id==cur_id).one()

    # Mentor lesson:
    cset = CanvasSet(
        role=MENTOR,
        curriculum_id=cur.id,
        start_datetime=cur.start_datetime, # start date doesn't really matter. 
        end_datetime=cur.end_datetime, # end date doesn't really matter. 
        description="Reconnect (New)",
        )

    local_db_session.add(cset)
    local_db_session.flush()
    print "Added cset id {0}".format(cset.id)

    # 1 of 2
    capp = CanvasApp(
        canvas_set_id=cset.id,
        ordinal=100,
        app_type=APP_TYPE_PRESENTATION,
        n_of_total=1,
        total=2,
        description="Here’s what your mentee did in class..."
        )

    local_db_session.add(capp)
    local_db_session.flush()
    print "Added capp id {0}".format(capp.id)

    # 1 of 1
    wid = Widget(
        canvas_app_id=capp.id,
        ordinal=100,
        )

    local_db_session.add(wid)
    local_db_session.flush()
    print "Added wid id {0}".format(wid.id)

    # 1 of 2
    widcon = WidgetContent(
        widget_id=wid.id,
        content_type=WIDGET_CONTENT_IMAGE,
        ordinal=100,
        url='//cdn.imentor.org/new_platform/static/canvas/images/Graduation_Quotes.jpg'
        )

    local_db_session.add(widcon)
    local_db_session.flush()
    print "Added widcon id {0}".format(widcon.id)

    # 2 of 2
    widcon = WidgetContent(
        widget_id=wid.id,
        content_type=WIDGET_CONTENT_HTML,
        ordinal=100,
        html='''
After reading the above quotes, your mentee discussed the following questions:
<ul>
<li>What do you think each of the quotes mean?</li>
<li>How might you apply this quote to your senior year in high school?</li>
</ul>
Next, the class reflected on their summer experiences.
            '''
        )

    local_db_session.add(widcon)
    local_db_session.flush()
    print "Added widcon id {0}".format(widcon.id)

    # 2 of 2
    capp = CanvasApp(
        canvas_set_id=cset.id,
        ordinal=200,
        app_type=APP_TYPE_PRESENTATION,
        n_of_total=2,
        total=2,
        description="Now it’s your turn"
        )

    local_db_session.add(capp)
    local_db_session.flush()
    print "Added capp id {0}".format(capp.id)

    # 1 of 1
    wid = Widget(
        canvas_app_id=capp.id,
        ordinal=100,
        )

    local_db_session.add(wid)
    local_db_session.flush()
    print "Added wid id {0}".format(wid.id)

    # 1 of 1
    widcon = WidgetContent(
        widget_id=wid.id,
        content_type=WIDGET_CONTENT_HTML,
        ordinal=100,
        html='''
<ul>
<li>Respond to your mentee’s summer highlights.</li>
<li>Share highlights from your summer. Be sure to answer your mentee’s questions. Remember to lead by example and provide clear details.</li>
<li>Share you what are most looking forward to this year.</li>
</ul>
            '''
        )

    local_db_session.add(widcon)
    local_db_session.flush()
    print "Added widcon id {0}".format(widcon.id)

    # Create a marker reference to the mentee's response, so the mentor can see 
    # the mentee's response.
    widconrmref = WidgetContentMarkerReference(
        widget_content_id = widcon.id,
        other_marker_id = mentee_content_to_attach_to['widget_content_respopnse_markers'][0],
        )

    local_db_session.add(widconrmref)
    local_db_session.flush()
    print "Added widconrmref id {0}".format(widconrmref.id)

    # Expecting a response form the mentor as well, so mark this.
    widconrm = WidgetContentResponseMarker(
        widget_content_id=widcon.id,
        response_type=APP_TYPE_PRESENTATION # Why we always default to this is beyond me.
        )

    local_db_session.add(widconrm)
    local_db_session.flush()
    print "Added widconrm id {0}".format(widconrm.id)

    # Create a marker reference IN THE FUTURE so the mentee can see the mentor's response 
    # to this lesson in the next lesson. Don't do it here, this isn't the
    # next lesson!

    #pprint.pprint( {'curriculum_id':cur.id, 'mentor_response_marker_for_next_lesson':[widconrm.id]} )
    return {'curriculum_id':cur.id, 'mentor_response_marker_for_next_lesson':[widconrm.id]}
