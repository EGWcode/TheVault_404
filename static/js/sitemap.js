/*
sitemap.js

Sitemap page created 10/19/2026 by Jaylen Belle


Description:
This makes the campus map on the sitemap page actually work physically.
It puts the pins on the map for the places listed in campus_locations.js file. 
It fills the list on the left side of the page with the search and filter buttons. 
Makes clicking a pin or list item bring up the building info. 
*/



const mapEl = document.getElementById("campusMap");
const listEl = document.getElementById("placeList");
const searchEl = document.getElementById("placeSearch");
const detailsEl = document.getElementById("placeDetails");

const pins = {};
let selectedId = null;
let activeFilter = "all";


/* Pins seciton */

CAMPUS_LOCATIONS.forEach(place=>{
    const pin = document.createElement("button");
    pin.className = "map-pin " + (place.type === "meetup" ? "pin-meetup" : "pin-building");
    pin.style.left = place.x + "%";
    pin.style.top = place.y + "%";
    pin.title = place.name;
    pin.setAttribute("aria-label", place.name);

    if(place.type === "meetup")
        pin.innerHTML = "&#9733;";

    pin.addEventListener("click", () => selectPlace(place.id));
    mapEl.appendChild(pin);
    pins[place.id] = pin;

});



/* Getting the list, search and filters buttons working */ 

function renderList() {
    const query = searchEl.value.trim().toLowerCase();
    listEl.innerHTML = "";

    CAMPUS_LOCATIONS.forEach(place => {
        const matchesFilter = activeFilter === "all" || place.type === activeFilter;
        const matchesSearch = place.name.toLowerCase().includes(query);
        const visible = matchesFilter && matchesSearch;

        pins[place.id].hidden =!visible;
        if (!visible) return;

        const li = document.createElement("li");
        li.className = "place-item" + (place.id === selectedId ? " active":"");
        li.innerHTML = ` <span class="place-dot ${place.type === "meetup" ? "dot-meetup" : "dot-building"}"></span> <span>${place.name}</span>`;
        li.addEventListener("click", () => selectPlace(place.id));
        listEl.appendChild(li);
    });

    if (!listEl.children.length) {
        listEl.innerHTML = `<li class="place-empty">No places match your search.</li>`;
    }
}




searchEl.addEventListener("input", renderList);

document.querySelectorAll(".filter-button").forEach(button =>{
    button.addEventListener("click", () => {
        document.querySelectorAll(".filter-button").forEach(b=> b.classList.remove("active"));
        button.classList.add("active");
        activeFilter = button.dataset.filter;
        renderList();
    });
});





/* Details panel */

function selectPlace(id) {
    const place = CAMPUS_LOCATIONS.find(p=>p.id === id);
    if (!place) return;



    if (selectedId)
        pins[selectedId].classList.remove("pin-selected");

    selectedId = id;
    pins[id].classList.add("pin-selected");

    showDetails(place);
    renderList();
    history.replaceState(null, "","#" + id);
}


function showDetails(place) {
    let html = `<button class="details-close" aria-label="Close details">&times;</button><p class="details-type">${place.type === "meetup" ? "&#9733; Recommended meetup spot" : "Campus building"}</p><h2>${place.name}</h2><p>${place.description}</p>`;

    if(place.meetup) {
        html += `<div class="details-meetup"><strong>Where to meet:</strong> ${place.meetup}</div>`;
    }

    if(place.hours) {
        html +=` <p class="details-hours"><strong>Hours:</strong> ${place.hours}</p>`;
    }


    if(place.levels && place.levels.length) {
        html += `<p class="levels-heading">Inside the building (${place.levels.length} level${place.levels.length > 1 ? "s" : ""})</p><div class="level-tabs">${place.levels.map((lvl, i) => `<button class="level-tab${i === 0 ? " active" :""}" data-level="${i}">${lvl.name}</button>`).join("")}</div><div class="level-body"></div>`;
        
    }

    detailsEl.innerHTML = html;
    detailsEl.hidden = false;

    detailsEl.querySelector(".details-close").addEventListener("click", clearSelection);

    if(place.levels && place.levels.length) {
        const showLevel = i => {
            const lvl = place.levels[i];
            detailsEl.querySelectorAll(".level-tab").forEach(t => t.classList.toggle("active", Number(t.dataset.level) === i));
            detailsEl.querySelector(".level-body").innerHTML = `<p>${lvl.note}</p>` + (lvl.image ? `<img src="${lvl.image}" alt="${lvl.name} floor plan" class="floor-plan"/>` :"");
        };

        detailsEl.querySelectorAll(".level-tab").forEach(tab => tab.addEventListener("click", () => showLevel(Number(tab.dataset.level))));
        showLevel(0);
    }


    document.querySelector(".sitemap-panel").scrollTop = 0;

    if (window.innerWidth <= 800)
        detailsEl.scrollIntoView({behavior: "smooth", block: "start"});

}



function clearSelection () {
    if (selectedId) pins[selectedId].classList.remove("pin-selected");
    selectedId = null;
    detailsEl.hidden = true;
    history.replaceState(null, "", location.pathname + location.search);
    renderList();
}

if (new URLSearchParams(location.search).get("pick") ==="1") {
    const readout = document.getElementById("pickReadout");
    readout.hidden =false;
    readout.textContent = "Pick mode: click the map to get x and y";

    mapEl.addEventListener("click", e => {
        if (e.target !== mapEl.querySelector(".campus-map-img"))
            return;

        const box = mapEl.getBoundingClientRect();
        const x = ((e.clientX - box.left) / box.width * 100).toFixed(1);
        const y = ((e.clientY - box.top) / box.height * 100).toFixed(1);
        const text = `x: ${x}, y: ${y}`;

        readout.textContent = text + " (copied)";
        if (navigator.clipboard)
            navigator.clipboard.writeText(text).catch(() => {});
    });
}




/* start*/
renderList();

if (location.hash)
    selectPlace(location.hash.slice(1));