"""
VTOP Sync — Playwright-based scraper using JavaScript injection.

Mirrors the approach used by android-vtop-chennai (VTOPService.java):
  - Loads VTOP pages in a real browser (Playwright / headless Chromium)
  - Injects JavaScript via page.evaluate() to interact with jQuery/AJAX
  - Extracts data from the live DOM, exactly as the Android app does

Reference: https://github.com/therealsujitk/android-vtop-chennai
"""

import getpass, base64, subprocess, sys, os, tempfile, json, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import get_connection, create_tables

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE_URL = "https://vtopcc.vit.ac.in/vtop"


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIN FLOW  (mirrors VTOPService.java: openSignIn → getCaptchaType →
#               getCaptcha → signIn)
# ═══════════════════════════════════════════════════════════════════════════════

def _launch_browser(playwright):
    """Launch headless Chromium with a realistic user-agent."""
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        ignore_https_errors=True,
    )
    page = context.new_page()
    return browser, context, page


def _navigate_to_login(page):
    """
    Step 1+2: Land on /vtop/login (landing page) and POST prelogin/setup.
    Mirrors VTOPService.openSignIn():
        $.ajax({ type:'POST', url:'/vtop/prelogin/setup',
                 data: $('#stdForm').serialize(), async: false })
    Then reload /vtop/login so the login form appears.
    """
    print("  📄 Navigating to VTOP landing page...")
    page.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=30000)

    # Detect page type — same check as VTOPService.onPageFinished
    page_type = page.evaluate("""() => {
        if (document.body === null) return 'BODY_NOT_READY';
        if (document.querySelector('input[id="authorizedIDX"]')) return 'HOME';
        if (document.querySelector('form[id="vtopLoginForm"]')) return 'LOGIN';
        return 'LANDING';
    }""")
    print(f"  🔍 Page type: {page_type}")

    if page_type == "LANDING":
        # POST prelogin/setup using jQuery (same JS as Android app)
        print("  🔄 POSTing prelogin/setup via $.ajax...")
        page.evaluate("""() => {
            $.ajax({
                type: 'POST',
                url: '/vtop/prelogin/setup',
                data: $('#stdForm').serialize(),
                async: false,
                success: function(res) {}
            });
        }""")
        # Reload login page — now the login form should appear
        page.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=30000)

    elif page_type == "LOGIN":
        # Already on the login page
        pass


def _detect_captcha_type(page):
    """
    Step 3: Detect whether VTOP uses default captcha or Google reCAPTCHA.
    Mirrors VTOPService.getCaptchaType():
        if ($('input[id="gResponse"]').length === 1) → GRECAPTCHA
        else → DEFAULT
    """
    result = page.evaluate("""() => {
        const response = { captcha_type: 'DEFAULT' };
        if (document.querySelectorAll('input[id="gResponse"]').length === 1) {
            response.captcha_type = 'GRECAPTCHA';
        }
        return response;
    }""")
    return result["captcha_type"]


def _get_default_captcha(page):
    """
    Step 4: Extract the captcha image as base64 data URI.
    Mirrors VTOPService.getCaptcha():
        return { captcha: $('#captchaBlock img').get(0).src }
    """
    result = page.evaluate("""() => {
        return {
            captcha: document.querySelector('#captchaBlock img')
                     ? document.querySelector('#captchaBlock img').src
                     : null
        };
    }""")
    captcha_src = result.get("captcha")

    if not captcha_src:
        # Fallback: any img with base64 data URI
        captcha_src = page.evaluate("""() => {
            const imgs = document.querySelectorAll('img');
            for (const img of imgs) {
                if (img.src && img.src.startsWith('data:image')) return img.src;
            }
            return null;
        }""")

    if not captcha_src:
        raise RuntimeError("Could not find captcha image in the page.")

    return captcha_src


def _sign_in(page, username, password, captcha):
    """
    Step 5: Fill credentials and submit via $.ajax POST to /vtop/login.
    Mirrors VTOPService.signIn() — the big evaluateJavascript block that:
      1. Fills username, password, captchaStr, gResponse via jQuery .val()
      2. Submits via $.ajax POST with $('#vtopLoginForm').serialize()
      3. Checks response for authorizedIDX or error patterns
    """
    # Escape single quotes in credentials for JS string injection
    u = username.replace("'", "\\'")
    p = password.replace("'", "\\'")
    c = captcha.replace("'", "\\'")

    result = page.evaluate(f"""() => {{
        // Fill form fields — same as VTOPService.signIn()
        $('#vtopLoginForm [name="username"]').val('{u}');
        $('#vtopLoginForm [name="password"]').val('{p}');
        $('#vtopLoginForm [name="captchaStr"]').val('{c}');
        $('#vtopLoginForm [name="gResponse"]').val('{c}');

        var response = {{
            authorised: false,
            error_message: null,
            error_code: 0
        }};

        $.ajax({{
            type: 'POST',
            url: '/vtop/login',
            data: $('#vtopLoginForm').serialize(),
            async: false,
            success: function(res) {{
                if (res.search('___INTERNAL___RESPONSE___') == -1) {{
                    $('#page_outline').html(res);
                    if (res.includes('authorizedIDX')) {{
                        response.authorised = true;
                        return;
                    }}
                    var pageContent = res.toLowerCase();
                    var invalidCaptchaRegex = new RegExp(/invalid\\s*captcha/);
                    var invalidCredentialsRegex = new RegExp(/invalid\\s*(user\\s*name|login\\s*id|user\\s*id)\\s*\\/\\s*password/);
                    var accountLockedRegex = new RegExp(/account\\s*is\\s*locked/);
                    var maxFailAttemptsRegex = new RegExp(/maximum\\s*fail\\s*attempts\\s*reached/);

                    if (invalidCaptchaRegex.test(pageContent)) {{
                        response.error_message = 'Invalid Captcha';
                        response.error_code = 1;
                    }} else if (invalidCredentialsRegex.test(pageContent)) {{
                        response.error_message = 'Invalid Username / Password';
                        response.error_code = 2;
                    }} else if (accountLockedRegex.test(pageContent)) {{
                        response.error_message = 'Your Account is Locked';
                        response.error_code = 3;
                    }} else if (maxFailAttemptsRegex.test(pageContent)) {{
                        response.error_message = 'Maximum login attempts reached';
                        response.error_code = 4;
                    }} else {{
                        response.error_message = 'Unknown login error';
                        response.error_code = 5;
                    }}
                }}
            }}
        }});
        return response;
    }}""")

    if result["authorised"]:
        # Reload to /vtop/content so the home page DOM is ready
        page.goto(f"{BASE_URL}/content", wait_until="networkidle", timeout=30000)
        print("  ✅ Logged in successfully!")
        return True
    else:
        code = result["error_code"]
        msg = result["error_message"]
        if code == 1:
            return False
        elif code == 2:
            raise ValueError(f"❌ {msg}")
        elif code == 3:
            raise ValueError(f"❌ {msg}")
        elif code == 4:
            raise ValueError(f"❌ {msg} — reset via browser")
        else:
            raise ValueError(f"❌ Login failed: {msg}")


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA EXTRACTION  (mirrors VTOPService.java: getSemesters, downloadCourses,
#                    downloadAttendance, downloadMarks, etc.)
# ═══════════════════════════════════════════════════════════════════════════════

def get_semesters(page):
    """
    Fetch available semesters from the Timetable page.
    Mirrors VTOPService.getSemesters():
        POST to 'academics/common/StudentTimeTableChn'
        Parse #semesterSubId <option> elements
    """
    result = page.evaluate("""() => {
        var data = 'verifyMenu=true&authorizedID=' + $('#authorizedIDX').val()
                 + '&_csrf=' + $('input[name="_csrf"]').val()
                 + '&nocache=@(new Date().getTime())';
        var response = {};
        $.ajax({
            type: 'POST',
            url: 'academics/common/StudentTimeTableChn',
            data: data,
            async: false,
            success: function(res) {
                if (res.toLowerCase().includes('time table')) {
                    var doc = new DOMParser().parseFromString(res, 'text/html');
                    var options = doc.getElementById('semesterSubId').getElementsByTagName('option');
                    var semesters = [];
                    for (var i = 0; i < options.length; ++i) {
                        if (!options[i].value) continue;
                        semesters.push({
                            name: options[i].innerText,
                            id: options[i].value
                        });
                    }
                    response.semesters = semesters;
                } else {
                    response.error = 'Could not load semesters';
                }
            }
        });
        return response;
    }""")

    if "error" in result:
        raise RuntimeError(result["error"])

    sems = {s["name"]: s["id"] for s in result["semesters"]}
    if not sems:
        raise RuntimeError("No semesters found")
    return sems


def download_courses(page, semester_id):
    """
    Download course list from the timetable page.
    Mirrors VTOPService.downloadCourses():
        POST to 'processViewTimeTable' with semesterSubId
        Parse the #studentDetailsList table
    """
    result = page.evaluate(f"""() => {{
        var data = 'semesterSubId={semester_id}'
                 + '&authorizedID=' + $('#authorizedIDX').val()
                 + '&_csrf=' + $('input[name="_csrf"]').val();
        var response = {{ courses: [] }};
        $.ajax({{
            type: 'POST',
            url: 'processViewTimeTable',
            data: data,
            async: false,
            success: function(res) {{
                var doc = new DOMParser().parseFromString(res, 'text/html');
                var table = doc.querySelector('#studentDetailsList table');
                if (!table) return;

                var headers = [];
                var ths = table.querySelectorAll('th');
                for (var i = 0; i < ths.length; i++) {{
                    headers.push(ths[i].innerText.trim().toLowerCase());
                }}

                function colIdx(keyword) {{
                    for (var j = 0; j < headers.length; j++) {{
                        if (headers[j].includes(keyword)) return j;
                    }}
                    return -1;
                }}

                var ci = colIdx('course');
                var cri = colIdx('l t p');
                var si = colIdx('slot');
                var fi = colIdx('faculty');
                if (ci === -1 || si === -1) return;

                var cells = table.querySelectorAll('td');
                var n = headers.length;
                for (var i = 0; ci + i < cells.length; i += n) {{
                    var raw = cells[ci + i].innerText.replace(/\\t/g, '').replace(/\\n/g, ' ').trim();
                    var slotVenue = cells[si + i].innerText.replace(/\\t/g, '').replace(/\\n/g, '');
                    var parts = raw.split('-');
                    var code = parts[0].trim();
                    var title = parts.length > 1 ? parts.slice(1).join('-').split('(')[0].trim() : raw;
                    var type = raw.toLowerCase().includes('lab') ? 'lab'
                             : raw.toLowerCase().includes('project') ? 'project' : 'theory';

                    var creditText = (cri !== -1 && cells[cri + i]) ? cells[cri + i].innerText.trim() : '';
                    var creditParts = creditText.split(/\\s+/);
                    var credits = creditParts.length > 0 ? parseInt(creditParts[creditParts.length - 1]) || 0 : 0;

                    var slotParts = slotVenue.split('-');
                    var slots = slotParts[0].trim().split('+');
                    var venue = slotParts.slice(1).join('-').trim();

                    var faculty = (fi !== -1 && cells[fi + i])
                                ? cells[fi + i].innerText.split('-')[0].trim() : '';

                    response.courses.push({{
                        code: code,
                        title: title,
                        type: type,
                        credits: credits,
                        slots: slots,
                        venue: venue,
                        faculty: faculty
                    }});
                }}
            }}
        }});
        return response;
    }}""")

    return result.get("courses", [])


def download_attendance(page, semester_id):
    """
    Download attendance data.
    Mirrors VTOPService.downloadAttendance():
        POST to 'processViewStudentAttendance'
        Parse #getStudentDetails table
    """
    result = page.evaluate(f"""() => {{
        var data = 'semesterSubId={semester_id}'
                 + '&authorizedID=' + $('#authorizedIDX').val()
                 + '&_csrf=' + $('input[name="_csrf"]').val();
        var response = {{ attendance: [] }};
        $.ajax({{
            type: 'POST',
            url: 'processViewStudentAttendance',
            data: data,
            async: false,
            success: function(res) {{
                var doc = new DOMParser().parseFromString(res, 'text/html');
                var table = doc.querySelector('#getStudentDetails');
                if (!table) return;

                var headers = [];
                var ths = table.querySelectorAll('th');
                for (var i = 0; i < ths.length; i++) {{
                    headers.push(ths[i].innerText.trim().toLowerCase());
                }}

                function colIdx(keyword) {{
                    for (var j = 0; j < headers.length; j++) {{
                        if (headers[j].includes(keyword)) return j;
                    }}
                    return -1;
                }}

                var si = colIdx('slot');
                var ai = colIdx('attended');
                var ti = colIdx('total');
                var pi = colIdx('percentage');
                var tyi = colIdx('course type');
                if (si === -1) return;

                var cells = table.querySelectorAll('td');
                var n = headers.length;
                for (var i = 0; si + i < cells.length; i += n) {{
                    response.attendance.push({{
                        slot: cells[si + i].innerText.trim().split('+')[0].trim(),
                        attended: parseInt(cells[ai + i].innerText.trim()) || 0,
                        total: parseInt(cells[ti + i].innerText.trim()) || 0,
                        percentage: parseInt(cells[pi + i].innerText.trim()) || 0,
                        course_type: (tyi !== -1 && cells[tyi + i].innerText.toLowerCase().includes('lab'))
                                     ? 'lab' : 'theory'
                    }});
                }}
            }}
        }});
        return response;
    }}""")

    return result.get("attendance", [])


def download_marks(page, semester_id):
    """
    Download marks/scores.
    VTOP structure discovered via debug:
      - Table 0 (class=customTable): course list. Row 0=header, Row 1+=course rows
        Columns: [Sl.No, ClassNbr, Course Code(2), Course Title(3), Course Type(4), ...]
      - Tables 1-N (class=customTable-level1): per-course marks. Row 0=header, Row 1+=marks
        Columns: [Sl.No(0), Mark Title(1), Max. Mark(2), Weightage %(3), Status(4),
                   Scored Mark(5), Weightage Mark(6), Class Average(7), ...]
      - ALL cells are <td>, zero <th> elements
    """
    # Step 1: Initialize marks page with verifyMenu
    page.evaluate("""() => {
        var data = 'verifyMenu=true&authorizedID=' + $('#authorizedIDX').val()
                 + '&_csrf=' + $('input[name="_csrf"]').val()
                 + '&nocache=@(new Date().getTime())';
        $.ajax({
            type: 'POST',
            url: 'examinations/doStudentMarkView',
            data: data,
            async: false,
            success: function(res) {}
        });
    }""")

    # Step 2: Fetch and parse marks
    result = page.evaluate(f"""() => {{
        var data = 'semesterSubId={semester_id}'
                 + '&authorizedID=' + $('#authorizedIDX').val()
                 + '&_csrf=' + $('input[name="_csrf"]').val();
        var response = {{ marks: [] }};
        $.ajax({{
            type: 'POST',
            url: 'examinations/doStudentMarkView',
            data: data,
            async: false,
            success: function(res) {{
                var doc = new DOMParser().parseFromString(res, 'text/html');
                var tables = doc.querySelectorAll('table');
                if (tables.length === 0) return;

                // Step A: Extract course codes from Table 0 (customTable)
                var courseTable = null;
                var marksTables = [];
                for (var t = 0; t < tables.length; t++) {{
                    if (tables[t].className.includes('customTable-level1')) {{
                        marksTables.push(tables[t]);
                    }} else if (tables[t].className.includes('customTable')) {{
                        courseTable = tables[t];
                    }}
                }}

                // Parse course codes from courseTable
                var courseCodes = [];
                if (courseTable) {{
                    var courseRows = courseTable.querySelectorAll(':scope > tbody > tr, :scope > tr');
                    // Find Course Code column index from header row (Row 0)
                    var headerCells = courseRows[0] ? courseRows[0].querySelectorAll('td') : [];
                    var codeCol = -1;
                    for (var h = 0; h < headerCells.length; h++) {{
                        var txt = headerCells[h].innerText.trim().toLowerCase();
                        if (txt.includes('course code') || txt === 'course code') {{
                            codeCol = h;
                            break;
                        }}
                    }}
                    if (codeCol === -1) codeCol = 2; // fallback

                    // Extract course codes from data rows
                    for (var r = 1; r < courseRows.length; r++) {{
                        var cells = courseRows[r].querySelectorAll(':scope > td');
                        if (cells.length >= 4) {{
                            var code = cells[codeCol] ? cells[codeCol].innerText.trim() : '';
                            // Only include rows that look like course data (have a proper course code)
                            if (code && /^[A-Z]{{2,4}}[0-9]{{3,4}}/.test(code)) {{
                                courseCodes.push(code);
                            }}
                        }}
                    }}
                }}

                // Step B: Parse each marks table (customTable-level1)
                for (var m = 0; m < marksTables.length; m++) {{
                    var courseCode = m < courseCodes.length ? courseCodes[m] : 'UNKNOWN';
                    var mRows = marksTables[m].querySelectorAll('tr');
                    if (mRows.length < 2) continue;

                    // Header is Row 0: [Sl.No., Mark Title, Max. Mark, Weightage %, Status, Scored Mark, ...]
                    // Find column indices dynamically from first row
                    var hCells = mRows[0].querySelectorAll('td');
                    var titleCol = 1, maxCol = 2, scoredCol = 5, weightageCol = 6, statusCol = 4;
                    for (var hi = 0; hi < hCells.length; hi++) {{
                        var ht = hCells[hi].innerText.trim().toLowerCase();
                        if (ht.includes('mark title') || ht === 'mark title') titleCol = hi;
                        else if (ht.includes('max') && ht.includes('mark')) maxCol = hi;
                        else if (ht.includes('scored') && ht.includes('mark')) scoredCol = hi;
                        else if (ht.includes('weightage') && ht.includes('mark')) weightageCol = hi;
                        else if (ht === 'status') statusCol = hi;
                    }}

                    // Data rows
                    for (var mr = 1; mr < mRows.length; mr++) {{
                        var mCells = mRows[mr].querySelectorAll('td');
                        if (mCells.length < 6) continue;

                        var markTitle = mCells[titleCol] ? mCells[titleCol].innerText.trim() : '';
                        var maxMark = mCells[maxCol] ? parseFloat(mCells[maxCol].innerText.trim()) : 0;
                        var scored = mCells[scoredCol] ? parseFloat(mCells[scoredCol].innerText.trim()) : 0;
                        var weightage = mCells[weightageCol] ? parseFloat(mCells[weightageCol].innerText.trim()) : 0;
                        var status = mCells[statusCol] ? mCells[statusCol].innerText.trim() : '';

                        if (markTitle && !isNaN(scored)) {{
                            response.marks.push({{
                                course_code: courseCode,
                                title: markTitle,
                                scored: scored,
                                max: maxMark,
                                weightage: weightage,
                                status: status
                            }});
                        }}
                    }}
                }}
            }}
        }});
        return response;
    }}""")

    return result.get("marks", [])


def download_exam_schedule(page, semester_id):
    """
    Download exam schedule.
    VTOP structure discovered via debug:
      - Single table (class=customTable), ALL <td>, zero <th>
      - Row 0 = header: [S.No., Course Code(1), Course Title(2), Course Type(3),
        Class ID(4), Slot(5), Exam Date(6), Exam Session(7), Reporting Time(8),
        Exam Time(9), Venue(10), Seat Location(11), Seat No.(12)]
      - Some rows are section labels like ['FAT'] with only 1 cell — skip those
      - Data rows have 13 columns
    """
    # Step 1: Initialize exam schedule page with verifyMenu
    page.evaluate("""() => {
        var data = 'verifyMenu=true&authorizedID=' + $('#authorizedIDX').val()
                 + '&_csrf=' + $('input[name="_csrf"]').val()
                 + '&nocache=@(new Date().getTime())';
        $.ajax({
            type: 'POST',
            url: 'examinations/doSearchExamScheduleForStudent',
            data: data,
            async: false,
            success: function(res) {}
        });
    }""")

    # Step 2: Fetch and parse exam schedule
    result = page.evaluate(f"""() => {{
        var data = 'semesterSubId={semester_id}'
                 + '&authorizedID=' + $('#authorizedIDX').val()
                 + '&_csrf=' + $('input[name="_csrf"]').val();
        var response = {{ exams: [] }};
        $.ajax({{
            type: 'POST',
            url: 'examinations/doSearchExamScheduleForStudent',
            data: data,
            async: false,
            success: function(res) {{
                var doc = new DOMParser().parseFromString(res, 'text/html');
                var tables = doc.querySelectorAll('table');
                if (tables.length === 0) return;

                var table = tables[0];
                var rows = table.querySelectorAll('tr');
                if (rows.length < 2) return;

                // Find column indices from header row (Row 0) — all <td>
                var hCells = rows[0].querySelectorAll('td');
                var codeCol = 1, titleCol = 2, typeCol = 3, dateCol = 6;
                var sessionCol = 7, reportCol = 8, timeCol = 9;
                var venueCol = 10, seatLocCol = 11, seatCol = 12;

                for (var h = 0; h < hCells.length; h++) {{
                    var ht = hCells[h].innerText.trim().toLowerCase();
                    if (ht.includes('course code')) codeCol = h;
                    else if (ht.includes('course title')) titleCol = h;
                    else if (ht.includes('course type')) typeCol = h;
                    else if (ht.includes('exam date')) dateCol = h;
                    else if (ht.includes('exam session')) sessionCol = h;
                    else if (ht.includes('reporting')) reportCol = h;
                    else if (ht.includes('exam time')) timeCol = h;
                    else if (ht === 'venue') venueCol = h;
                    else if (ht.includes('seat location')) seatLocCol = h;
                    else if (ht.includes('seat no')) seatCol = h;
                }}

                var currentExamType = '';
                for (var r = 1; r < rows.length; r++) {{
                    var cells = rows[r].querySelectorAll('td');

                    // Section label rows (e.g. 'FAT', 'CAT-I') have 1-2 cells
                    if (cells.length <= 3) {{
                        var label = cells[0] ? cells[0].innerText.trim() : '';
                        if (label) currentExamType = label;
                        continue;
                    }}

                    // Data row — must have enough columns
                    if (cells.length < 7) continue;

                    response.exams.push({{
                        code: cells[codeCol] ? cells[codeCol].innerText.trim() : '',
                        title: cells[titleCol] ? cells[titleCol].innerText.trim() : '',
                        exam: currentExamType,
                        date: cells[dateCol] ? cells[dateCol].innerText.trim() : '',
                        session: cells[sessionCol] ? cells[sessionCol].innerText.trim() : '',
                        time: cells[timeCol] ? cells[timeCol].innerText.trim() : '',
                        venue: cells[venueCol] ? cells[venueCol].innerText.trim() : '',
                        seat: cells[seatCol] ? cells[seatCol].innerText.trim() : ''
                    }});
                }}
            }}
        }});
        return response;
    }}""")

    return result.get("exams", [])


def download_profile(page):
    """
    Download student name and CGPA.
    Mirrors VTOPService.getName() and getCreditsCGPA().
    """
    profile = page.evaluate("""() => {
        var data = 'verifyMenu=true&authorizedID=' + $('#authorizedIDX').val()
                 + '&_csrf=' + $('input[name="_csrf"]').val()
                 + '&nocache=@(new Date().getTime())';
        var response = { name: '', cgpa: 0, total_credits: 0 };

        // Get name from StudentProfileAllView
        $.ajax({
            type: 'POST',
            url: 'studentsRecord/StudentProfileAllView',
            data: data,
            async: false,
            success: function(res) {
                if (res.toLowerCase().includes('personal information')) {
                    var doc = new DOMParser().parseFromString(res, 'text/html');
                    var cells = doc.getElementsByTagName('td');
                    for (var i = 0; i < cells.length; ++i) {
                        var key = cells[i].innerText.toLowerCase();
                        if (key.includes('student') && key.includes('name')) {
                            response.name = cells[++i].innerHTML.trim();
                            break;
                        }
                    }
                }
            }
        });

        // Get CGPA from StudentGradeHistory
        $.ajax({
            type: 'POST',
            url: 'examinations/examGradeView/StudentGradeHistory',
            data: data,
            async: false,
            success: function(res) {
                var doc = new DOMParser().parseFromString(res, 'text/html');
                var tables = doc.getElementsByTagName('table');
                for (var i = tables.length - 1; i >= 0; --i) {
                    var headings = tables[i].getElementsByTagName('tr')[0].getElementsByTagName('td');
                    if (headings.length === 0) continue;
                    if (headings[0].innerText.toLowerCase().includes('credits')) {
                        var creditsIndex, cgpaIndex;
                        for (var j = 0; j < headings.length; ++j) {
                            var heading = headings[j].innerText.toLowerCase();
                            if (heading.includes('earned')) {
                                creditsIndex = j + headings.length;
                            } else if (heading.includes('cgpa')) {
                                cgpaIndex = j + headings.length;
                            }
                        }
                        var allCells = tables[i].getElementsByTagName('td');
                        if (cgpaIndex !== undefined)
                            response.cgpa = parseFloat(allCells[cgpaIndex].innerText) || 0;
                        if (creditsIndex !== undefined)
                            response.total_credits = parseFloat(allCells[creditsIndex].innerText) || 0;
                        break;
                    }
                }
            }
        });

        return response;
    }""")

    return profile


# ═══════════════════════════════════════════════════════════════════════════════
#  DATABASE SAVE
# ═══════════════════════════════════════════════════════════════════════════════

def save_to_db(courses, attendance, marks=None, exams=None, profile=None):
    """Save all scraped data into the SQLite database."""
    create_tables()
    conn = get_connection()
    cur = conn.cursor()

    # Delete in child-first order to respect foreign keys
    # timetable refs slots+courses, attendance refs courses, slots refs courses
    cur.execute("DELETE FROM timetable")
    cur.execute("DELETE FROM attendance")
    cur.execute("DELETE FROM slots")
    cur.execute("DELETE FROM marks")
    cur.execute("DELETE FROM exams")
    cur.execute("DELETE FROM assignments")
    cur.execute("DELETE FROM staff")
    cur.execute("DELETE FROM courses")

    # Save profile if available
    if profile:
        cur.execute("DELETE FROM profile")
        cur.execute(
            "INSERT INTO profile (id, name, cgpa, total_credits) VALUES (?,?,?,?)",
            (1, profile.get("name", ""), profile.get("cgpa", 0), profile.get("total_credits", 0))
        )

    cid = 1
    sid = 1
    slot_map = {}
    for c in courses:
        cur.execute(
            "INSERT INTO courses VALUES (?,?,?,?,?,?,?)",
            (cid, c["code"], c["title"], c["type"], c["credits"], c["venue"], c["faculty"])
        )
        for s in c.get("slots", []):
            s = s.strip()
            if s:
                cur.execute("INSERT INTO slots VALUES (?,?,?)", (sid, s, cid))
                slot_map[s] = cid
                sid += 1
        cid += 1

    for i, a in enumerate(attendance):
        cid2 = slot_map.get(a["slot"])
        if cid2:
            cur.execute(
                "INSERT INTO attendance VALUES (?,?,?,?,?)",
                (i + 1, cid2, a["attended"], a["total"], a["percentage"])
            )

    # Save marks — match by course code to course id
    if marks:
        code_to_id = {}
        for row in cur.execute("SELECT id, code FROM courses").fetchall():
            code_to_id[row[0]] = row[1]
        id_by_code = {v: k for k, v in code_to_id.items()}

        for i, m in enumerate(marks):
            cid3 = id_by_code.get(m.get("course_code", ""))
            if cid3:
                cur.execute(
                    "INSERT INTO marks VALUES (?,?,?,?,?,?)",
                    (i + 1, cid3, m["title"], m["scored"], m["max"], 0)
                )

    # Save exams — match by course code to course id
    if exams:
        if not marks:  # rebuild id_by_code if not done above
            code_to_id = {}
            for row in cur.execute("SELECT id, code FROM courses").fetchall():
                code_to_id[row[0]] = row[1]
            id_by_code = {v: k for k, v in code_to_id.items()}

        for i, e in enumerate(exams):
            cid4 = id_by_code.get(e.get("code", ""))
            if cid4:
                cur.execute(
                    "INSERT INTO exams VALUES (?,?,?,?,?,?,?)",
                    (i + 1, cid4, e.get("exam", ""), e.get("date", ""),
                     e.get("time", ""), e.get("venue", ""), e.get("seat", ""))
                )

    conn.commit()
    conn.close()
    print(f"  ✅ Saved {len(courses)} courses, {len(attendance)} attendance, "
          f"{len(marks or [])} marks, {len(exams or [])} exams to DB")


# ═══════════════════════════════════════════════════════════════════════════════
#  INTERACTIVE CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print("  VIT VTOP Sync (Playwright — WebView-style JS injection)")
    print("=" * 55)

    username = input("VTOP Username (Reg No): ").strip()
    password = getpass.getpass("VTOP Password: ")

    with sync_playwright() as pw:
        print("\n🔄 Launching browser...")
        browser, context, page = _launch_browser(pw)

        try:
            # ── Step 1–2: Navigate & prelogin/setup ──
            _navigate_to_login(page)

            # ── Step 3: Detect captcha type ──
            captcha_type = _detect_captcha_type(page)
            print(f"  🔐 Captcha type: {captcha_type}")

            if captcha_type == "DEFAULT":
                import ddddocr
                ocr = ddddocr.DdddOcr(show_ad=False)
                
                max_retries = 10
                for attempt in range(max_retries):
                    if attempt > 0:
                        print(f"  🔄 Retrying login (Attempt {attempt + 1}/{max_retries})...")
                        _navigate_to_login(page)
                    
                    # ── Step 4: Extract captcha image ──
                    captcha_src = _get_default_captcha(page)
                    print("  ✅ Captcha image extracted")

                    captcha_data = captcha_src.split(",")[1]
                    img_bytes = base64.b64decode(captcha_data)
                    
                    # Solve via OCR
                    captcha_answer = ocr.classification(img_bytes).strip().upper()
                    print(f"  🤖 OCR read: {captcha_answer}")
                    
                    # ── Step 5: Sign in ──
                    print("  🔐 Logging in...")
                    if _sign_in(page, username, password, captcha_answer):
                        break
                    else:
                        print("  ❌ OCR guess was wrong (Invalid Captcha).")
                else:
                    raise ValueError("Failed to bypass captcha after 10 attempts.")

            elif captcha_type == "GRECAPTCHA":
                print("  ⚠️  Google reCAPTCHA detected — manual solve needed")
                print("     Opening browser window for you to solve reCAPTCHA...")
                # For reCAPTCHA, we need to show the browser
                browser.close()
                browser = pw.chromium.launch(headless=False)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    ignore_https_errors=True,
                )
                page = context.new_page()
                _navigate_to_login(page)

                # Execute reCAPTCHA — mirrors VTOPService.executeCaptcha()
                page.evaluate("""() => {
                    function callBuiltValidation(token) {
                        document.getElementById('gResponse').value = token;
                    }
                    var executeInterval = setInterval(function() {
                        try {
                            grecaptcha.execute();
                            clearInterval(executeInterval);
                        } catch (err) {}
                    }, 500);
                }""")

                captcha_answer = input("🔤 Solve reCAPTCHA in the browser, then press Enter: ").strip()
                # Get the gResponse value
                captcha_answer = page.evaluate("() => document.getElementById('gResponse').value")
                
                # ── Step 5: Sign in ──
                print("🔐 Logging in...")
                _sign_in(page, username, password, captcha_answer)

            # ── Step 6: Get semesters ──
            print("📅 Fetching semesters...")
            sems = get_semesters(page)
            for i, name in enumerate(sems):
                print(f"  [{i}] {name}")
            ch = int(input("Select semester: "))
            sem_name = list(sems.keys())[ch]
            sem_id = sems[sem_name]
            print(f"  ✅ {sem_name}")

            # ── Step 7: Download profile ──
            print("👤 Downloading profile...")
            profile = download_profile(page)
            if profile.get("name"):
                print(f"  ✅ Name: {profile['name']}")
            if profile.get("cgpa"):
                print(f"  ✅ CGPA: {profile['cgpa']} | Credits: {profile['total_credits']}")

            # ── Step 8: Download courses ──
            print("📚 Downloading courses...")
            courses = download_courses(page, sem_id)
            print(f"  ✅ {len(courses)} courses")
            for c in courses:
                print(f"     {c['code']} — {c['title']} ({c['type']})")

            # ── Step 9: Download attendance ──
            print("📊 Downloading attendance...")
            att = download_attendance(page, sem_id)
            print(f"  ✅ {len(att)} records")

            # ── Step 10: Download marks ──
            print("📝 Downloading marks...")
            marks = download_marks(page, sem_id)
            print(f"  ✅ {len(marks)} marks")

            # ── Step 11: Download exam schedule ──
            print("📋 Downloading exam schedule...")
            exams = download_exam_schedule(page, sem_id)
            print(f"  ✅ {len(exams)} exams")

            # ── Step 12: Save everything ──
            print("💾 Saving to database...")
            save_to_db(courses, att, marks, exams, profile)

            print("\n✅ Sync complete!")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            raise
        finally:
            browser.close()
