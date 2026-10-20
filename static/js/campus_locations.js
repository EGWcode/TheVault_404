


















const CAMPUS_LOCATIONS = [
    {
        id: "student-center",
        name: "Student Center",
        type: "meetup",
        x:41.2, y:44.4,
        description: "This is the center of student life, it has many food opions, seats, louges, and rooms. It's normaly a busy place during the day, so I would be a good public place to meet at with good lighting.",
        meetup: "You can meet in the middle of the STU or where ever there is seating to check your items",
        hours: "M - F: 8AM - 9PM, Sat: 12pm - 9PM, Sun: 2pm - 7pm",
        levels: [
            {name: "Level 1", note: "Main entrance, lobby, food court, and seating areas."},
            {name: "Level 2", note: "Gym, students lounges, work rooms, and faculty offices."},
            {name: "Level 3", note: "mini track, and conference rooms."}
        ]
    },

    {
        id: "library",
        name: "Williams R & Norma B. Harvey Library",
        type: "meetup",
        x:30.1, y:29.6,
        description: "Hampton Universities main library with study rooms, main computer lab/help center, and research help.",
        meetup: "You can meet on the first floor where there are staff and good lighting.",
        hours: "Mon - Thr: 8AM - 1AM, Fri: 8AM - 5PM, Sat: 9AM - 5PM, Sun: 2PM - 1AM",
        levels: [
            {name: "Level 1", note: "Administration, the 24-hour study room, and group study rooms."},
            {name: "Level 2", note: "Quiet study areas, and books"},
            {name: "Level 3", note: "Group study rooms, and the peabody room."},
            {name: "Level 4", note: "Group study rooms, books, and specialized offices."},
            {name: "Level 5", note: "Academic technology mall and computer lab/help center, "}
        ] 
    },

    {
        id: "bookstore",
        name: "University College & Bookstore",
        type: "meetup",
        x: 14.3, y: 27.4,
        description: "The universtiy bookstore with textbooks, apperal, general supplies.",
        meetup: "You can meet outside the bookstore enterance, preferabliy during open hours when staff is there.",
        hours: "Mon - Fri: 9AM - 5PM, Sat: 10AM - 2PM, Sun: Closed"
    },

    {
        id: "convocation-center",
        name: "Convocation Center",
        type: "building",
        x: 63.2, y:18.1,
        description: "The multi purpose arena used for mainly basketball games, concerts, parties, graducation, and carrer fairs.",
        hours: "Mon - Sat: Open 24 hours, Sun: Closed"
    }
];