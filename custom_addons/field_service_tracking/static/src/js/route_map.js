/** @odoo-module **/

import { Component, useRef, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { session } from "@web/session";

class GpsTrackingMap extends Component {
    setup() {
        this.mapRef = useRef("map");
        this.state = useState({
            date: new Date().toISOString().split("T")[0],
            employeeId: session.is_system ? null : session.user_id.employee_id,
            isAdmin: session.is_system,
            loading: true,
            info: null,
            employees: [],
        });

        onMounted(async () => {
            await this.loadEmployeeData();
            await this.renderMap();
        });
    }

    async loadEmployeeData() {
        const { date, employeeId } = this.state;

        const res = await jsonrpc("/live/gps/employees_data", {
            date_str: date,
            employee_id: parseInt(employeeId),
        });

        if (res.error) {
            console.error("❌ Failed to load employee data", res.error);
////////////////////////////////////////////////////////////////////////////////////////

            if (res.error.includes("GPS tracking is disabled")) {
                this.state.info = {
                    error: res.error,
                    gps_disabled: true
                };
            }
////////////////////////////////////////////////////////////////////////////////////////
            return;
        }

        this.state.employees = res.employees || [];
        this.state.info = res.employee_info || {};

        if (!this.state.employeeId && res.employee_info?.id) {
            this.state.employeeId = res.employee_info.id;
        }
    }

    // Enhanced clustering function to group nearby points properly
    clusterNearbyPoints(data, threshold = 0.0001) { // ~11 meters
        const clusters = [];
        const processed = new Set();

        data.forEach((point, index) => {
            if (processed.has(index)) return;

            const cluster = [index];
            processed.add(index);

            // Find nearby points
            for (let i = index + 1; i < data.length; i++) {
                if (processed.has(i)) continue;

                const distance = this.calculateDistance(
                    data[index].lat, data[index].lng,
                    data[i].lat, data[i].lng
                );

                if (distance <= threshold) {
                    cluster.push(i);
                    processed.add(i);
                }
            }

            clusters.push(cluster);
        });

        return clusters;
    }

    // Calculate distance between two points (Haversine formula)
    calculateDistance(lat1, lng1, lat2, lng2) {
        const R = 6371e3; // Earth's radius in meters
        const φ1 = lat1 * Math.PI / 180;
        const φ2 = lat2 * Math.PI / 180;
        const Δφ = (lat2 - lat1) * Math.PI / 180;
        const Δλ = (lng2 - lng1) * Math.PI / 180;

        const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
                  Math.cos(φ1) * Math.cos(φ2) *
                  Math.sin(Δλ/2) * Math.sin(Δλ/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

        return R * c;
    }

    // Check if travel between two points is physically impossible
    isSuspiciousTravel(point1, point2) {
        if (!point1.timestamp || !point2.timestamp) return false;

        const distance = this.calculateDistance(point1.lat, point1.lng, point2.lat, point2.lng);
        const time1 = new Date(point1.timestamp);
        const time2 = new Date(point2.timestamp);
        const timeDiffSeconds = Math.abs(time2 - time1) / 1000;
        const timeDiffHours = timeDiffSeconds / 3600;

        // If no time difference, not suspicious
        if (timeDiffSeconds < 10) return false;

        // Calculate required speed in km/h
        const requiredSpeedKmh = (distance / 1000) / timeDiffHours;

        // Suspicious if speed > 120 km/h (considering two-wheeler mode)
        // Also suspicious if significant distance (>50km) covered in very short time (<300 seconds = 5 minutes)
        const isHighSpeed = requiredSpeedKmh > 120;
        const isTeleportation = distance > 50000 && timeDiffSeconds < 300; // 50km in 5 minutes

        if (isHighSpeed || isTeleportation) {
            console.log(`🚨 Suspicious travel detected: ${(distance/1000).toFixed(2)}km in ${timeDiffSeconds}s = ${requiredSpeedKmh.toFixed(2)} km/h`);
            return true;
        }

        return false;
    }

    // Enhanced function to detect suspicious points including start/end points
    detectSuspiciousPoints(data) {
        const suspiciousPoints = new Set();

        // Check each point for suspicious travel from previous point
        for (let i = 1; i < data.length; i++) {
            if (this.isSuspiciousTravel(data[i-1], data[i])) {
                // Mark both points as suspicious for extreme cases
                suspiciousPoints.add(i-1);
                suspiciousPoints.add(i);
            }
        }

        // Mark points as suspicious in the data
        suspiciousPoints.forEach(index => {
            data[index].suspicious = true;
            data[index].suspiciousReason = "Impossible travel speed/distance";
        });

        return data;
    }

    // Apply smart jitter only to clustered points (not suspicious ones)
    applySmartJitter(data) {
        const clusters = this.clusterNearbyPoints(data);

        clusters.forEach(cluster => {
            if (cluster.length > 1) {
                // Only apply jitter if points are not already marked as suspicious
                const hasOriginalSuspicious = cluster.some(idx => data[idx].suspicious === true);

                if (!hasOriginalSuspicious) {
                    // Find cluster center
                    const centerLat = cluster.reduce((sum, idx) => sum + data[idx].lat, 0) / cluster.length;
                    const centerLng = cluster.reduce((sum, idx) => sum + data[idx].lng, 0) / cluster.length;

                    // Apply circular jitter around center
                    cluster.forEach((pointIdx, clusterIdx) => {
                        if (clusterIdx > 0) { // Keep first point as is
                            const angle = (2 * Math.PI * clusterIdx) / cluster.length;
                            const jitter = 0.00003; // ~3 meters

                            // Store original coordinates
                            data[pointIdx].originalLat = data[pointIdx].lat;
                            data[pointIdx].originalLng = data[pointIdx].lng;

                            // Apply jitter
                            data[pointIdx].lat = centerLat + Math.cos(angle) * jitter;
                            data[pointIdx].lng = centerLng + Math.sin(angle) * jitter;

                            // Mark as jittered (not suspicious)
                            data[pointIdx].isJittered = true;
                        }
                    });
                }
            }
        });

        return data;
    }

    async renderMap() {
        const container = this.mapRef.el;
        if (!container) return;

        this.state.loading = true;

        const { date, employeeId, isAdmin } = this.state;
        if (isAdmin && !employeeId) {
            this.state.loading = false;
            return;
        }
//////////////////////////////////////////////////////////////////////////////////////////
        // Check if GPS tracking is disabled
        if (this.state.info?.gps_disabled) {
            this.state.loading = false;
            container.innerHTML = `
                <div style="display: flex; justify-content: center; align-items: center; height: 400px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px;">
                    <div style="text-align: center; color: #6c757d;">
                        <h4>GPS Tracking Disabled</h4>
                        <p>${this.state.info.error}</p>
                        <p>Please contact your administrator to enable GPS tracking.</p>
                    </div>
                </div>
            `;
            return;
        }
////////////////////////////////////////////////////////////////////////////////////////////

        const [apiKey, gpsDataResp] = await Promise.all([
            jsonrpc("/get/google/maps/api/key", {}),
            jsonrpc("/live/gps/path", { date_str: date, employee_id: employeeId }),
        ]);

        this.state.loading = false;

///////////////////////////////////////////////////////////////////////////////////////////

        // Handle GPS tracking disabled error from API key endpoint (API key fetch request)
        if (apiKey.error && apiKey.error.includes("GPS tracking is disabled")) {
            container.innerHTML = `
                <div style="display: flex; justify-content: center; align-items: center; height: 400px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px;">
                    <div style="text-align: center; color: #6c757d;">
                        <h4>GPS Tracking Disabled</h4>
                        <p>${apiKey.error}</p>
                        <p>Please contact your administrator to enable GPS tracking.</p>
                    </div>
                </div>
            `;
            return;
        }

        // Handle GPS path data errors (GPS path data fetch request)
        if (gpsDataResp.error && gpsDataResp.error.includes("GPS tracking is disabled")) {
            container.innerHTML = `
                <div style="display: flex; justify-content: center; align-items: center; height: 400px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px;">
                    <div style="text-align: center; color: #6c757d;">
                        <h4>GPS Tracking Disabled</h4>
                        <p>${gpsDataResp.error}</p>
                        <p>Please contact your administrator to enable GPS tracking.</p>
                    </div>
                </div>
            `;
            return;
        }
///////////////////////////////////////////////////////////////////////////////////////////

        // Handle new response format
        const gpsData = gpsDataResp.points || gpsDataResp;
        this.state.info.speed_kmh = gpsDataResp.speed_kmh;
        this.state.info.traveled_duration = gpsDataResp.traveled_duration;
        this.state.info.speed_is_unusual = gpsDataResp.speed_kmh > 100;

        // Handle suspicious points more carefully
        this.state.info.any_suspicious = gpsDataResp.any_suspicious;

        if (gpsDataResp.duration_s) {
            const totalSeconds = Math.floor(gpsDataResp.duration_s);
            const hours = Math.floor(totalSeconds / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            const seconds = totalSeconds % 60;
            this.state.info.duration = [
                hours.toString().padStart(2, '0'),
                minutes.toString().padStart(2, '0'),
                seconds.toString().padStart(2, '0')
            ].join(':');
        } else {
            this.state.info.duration_s = null;
        }

        if (!gpsData || gpsData.length < 2) {
            this.state.info.distance = null;
            this.state.info.duration = null;
//////////////////////////////////////////////////////////////////////////////////////////

            container.innerHTML = `
                <div style="display: flex; justify-content: center; align-items: center; height: 400px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px;">
                    <div style="text-align: center; color: #6c757d;">
                        <h4>No GPS Data Found</h4>
                        <p>No GPS tracking data found for the selected date.</p>
                        <p>Make sure GPS tracking was active during attendance.</p>
                    </div>
                </div>
            `;
            return;
//////////////////////////////////////////////////////////////////////////////////////////


        }

        if (!window.google || !window.google.maps) {
            const script = document.createElement("script");
            script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey.api_key}&libraries=marker&v=weekly`;
            script.async = true;
            script.defer = true;
            script.onload = () => this.initMap(container, gpsData);
            document.head.appendChild(script);
        } else {
            this.initMap(container, gpsData);
        }
    }

    async initMap(container, data) {
        if (!Array.isArray(data) || data.length < 2) return;

        // First, detect suspicious points based on travel patterns
        const dataWithSuspiciousDetection = this.detectSuspiciousPoints([...data]);

        // Then apply smart jitter to handle overlapping points (but preserve suspicious ones)
        const processedData = this.applySmartJitter(dataWithSuspiciousDetection);

        // Update suspicious info based on our detection
        this.state.info.any_suspicious = processedData.some(p => p.suspicious === true);

        const origin = { lat: processedData[0].lat, lng: processedData[0].lng };
        const destination = {
            lat: processedData[processedData.length - 1].lat,
            lng: processedData[processedData.length - 1].lng
        };

        const map = new google.maps.Map(container, {
            zoom: 14,
            center: origin,
            mapId: "DEMO_MAP_ID",
            gestureHandling: "cooperative",
        });

        // Create markers with enhanced categorization
        processedData.forEach((p, i) => {
            const marker = new google.maps.marker.AdvancedMarkerElement({
                map,
                position: { lat: p.lat, lng: p.lng },
//                content: (() => {
//                    const el = document.createElement("div");
//
//                    // Enhanced color coding logic
//                    if (p.suspicious === true && !p.isJittered) {
//                        // Genuinely suspicious points (including start/end if impossible travel)
//                        el.style.backgroundColor = "purple";
//                        el.style.border = "2px solid red";
//                        el.title = "Suspicious Point - Impossible Travel";
//                    } else if (i === 0 && p.suspicious === true) {
//                        // Suspicious start point
//                        el.style.backgroundColor = "purple";
//                        el.style.border = "2px solid green";
//                        el.title = "Suspicious Start Point";
//                    } else if (i === processedData.length - 1 && p.suspicious === true) {
//                        // Suspicious end point
//                        el.style.backgroundColor = "purple";
//                        el.style.border = "2px solid red";
//                        el.title = "Suspicious End Point";
//                    } else if (i === 0) {
//                        // Normal start point
//                        el.style.backgroundColor = "green";
//                        el.title = "Start Point";
//                    } else if (i === processedData.length - 1) {
//                        // Normal end point
//                        el.style.backgroundColor = "red";
//                        el.title = "End Point";
//                    } else if (p.isJittered) {
//                        // Clustered/jittered points
//                        el.style.backgroundColor = "orange";
//                        el.title = "Clustered Point";
//                    } else {
//                        // Normal route points
//                        el.style.backgroundColor = "yellow";
//                        el.title = "Route Point";
//                    }
//
//                    el.style.width = el.style.height = "12px";
//                    el.style.borderRadius = "50%";
//                    el.style.boxShadow = "0 0 3px #000";
//                    return el;
//                })(),

                content: (() => {
                    const el = document.createElement("div");

                    const circle = document.createElement("div");
                    const label = document.createElement("span");

                    let isCallPoint = false;

                    // Suspicious / jitter / route handling
                    if (p.suspicious === true && !p.isJittered) {
                        if (i === 0) {
                            circle.style.backgroundColor = "purple";
                            circle.style.border = "2px solid green";
                            circle.title = "Suspicious Start Point";
                        } else if (i === processedData.length - 1) {
                            circle.style.backgroundColor = "purple";
                            circle.style.border = "2px solid red";
                            circle.title = "Suspicious End Point";
                        } else {
                            circle.style.backgroundColor = "purple";
                            circle.style.border = "2px solid red";
                            circle.title = "Suspicious Point - Impossible Travel";
                        }
                    } else if (p.isJittered) {
                        circle.style.backgroundColor = "orange";
                        circle.title = "Clustered Point";
                    }
                    // Call start / end = red pin only (no bg circle, no number)
                    else if (p.tracking_type === "call_start") {
                        isCallPoint = true;
                        circle.innerHTML = "📍";
                        circle.style.fontSize = "22px";
                        circle.title = "Call Start Point";
                    } else if (p.tracking_type === "call_end") {
                        isCallPoint = true;
                        circle.innerHTML = "📍";
                        circle.style.fontSize = "22px";
                        circle.title = "Call End Point";
                    }
                    // Normal route points
                    else if (i === 0) {
                        circle.style.backgroundColor = "green";
                        circle.title = "Start Point";
                    } else if (i === processedData.length - 1) {
                        circle.style.backgroundColor = "red";
                        circle.title = "End Point";
                    } else {
                        circle.style.backgroundColor = "yellow";
                        circle.title = "Route Point";
                    }

                    // Common styles
                    circle.style.display = "flex";
                    circle.style.alignItems = "center";
                    circle.style.justifyContent = "center";
                    circle.style.position = "relative";

                    if (!isCallPoint) {
                        // Circle shape only for non-call points
                        circle.style.width = "22px";
                        circle.style.height = "22px";
                        circle.style.borderRadius = "50%";
                        circle.style.boxShadow = "0 0 3px #000";
                        circle.style.fontSize = "11px";
                        circle.style.color = "black";
                        circle.style.fontWeight = "bold";
                    }

                    // Number inside circle
                    label.textContent = (i + 1).toString();
                    circle.appendChild(label);
                    el.appendChild(circle);
                    return el;

                })(),

            });

            // Enhanced info window with suspicious details
            const infoWindow = new google.maps.InfoWindow({
                content: `
                    <div>
                        <strong>Position:</strong> ${i + 1}/${processedData.length}<br/>
                        <strong>Lat:</strong> ${p.originalLat || p.lat}<br/>
                        <strong>Lng:</strong> ${p.originalLng || p.lng}<br/>
                        <strong>Time:</strong> ${p.timestamp ? p.timestamp.replace('T', ' ').replace('Z', '') : ''}<br/>
                        <strong>Type:</strong> ${p.tracking_type}<br/>
                        ${p.isJittered ? '<span style="color:orange;font-weight:bold;">Clustered Point</span><br/>' : ''}
                        ${p.suspicious === true ? `<span style="color:red;font-weight:bold;">⚠️ SUSPICIOUS!</span><br/><span style="color:red;font-size:12px;">${p.suspiciousReason || 'Unknown reason'}</span><br/>` : ''}
                    </div>
                `
            });

            marker.addListener("click", () => {
                infoWindow.open({
                    anchor: marker,
                    map,
                    shouldFocus: false,
                });
            });

        });

        // Create route using original coordinates (not jittered)
        const routeData = data.map(p => ({ lat: p.lat, lng: p.lng }));
        const routeOrigin = routeData[0];
        const routeDestination = routeData[routeData.length - 1];

        const directions = new google.maps.DirectionsService();
        const renderer = new google.maps.DirectionsRenderer({
            suppressMarkers: true,
            polylineOptions: {
                strokeColor: this.state.info.any_suspicious ? "#ff5733" : "#53ff1a", // Red if suspicious
                strokeWeight: 5,
            },
        });
        renderer.setMap(map);

        directions.route(
            {
                origin: routeOrigin,
                destination: routeDestination,
                waypoints: routeData.slice(1, -1).map(p => ({
                    location: { lat: p.lat, lng: p.lng },
                    stopover: false
                })),
                travelMode: google.maps.TravelMode.WALKING,
            },
            (res, status) => {
                if (status === "OK") renderer.setDirections(res);
            }
        );

        // Calculate Distance & Duration using DistanceMatrixService
        const matrixService = new google.maps.DistanceMatrixService();
        matrixService.getDistanceMatrix({
            origins: [routeOrigin],
            destinations: [routeDestination],
            travelMode: google.maps.TravelMode.TWO_WHEELER  ,
            unitSystem: google.maps.UnitSystem.METRIC,
        }, (response, status) => {
            if (status === "OK") {
                const result = response.rows[0].elements[0];
                if (result.status === "OK") {
                    this.state.info.distance = result.distance.text;
                    this.state.info.duration = result.duration.text;
                }
            } else {
                console.error("❌ DistanceMatrix failed:", status);
            }
        });
    }

    async onChangeFilter(ev) {
        const name = ev.target.name;
        const value = ev.target.value;
        this.state[name] = value;
        await this.loadEmployeeData();
        await this.renderMap();
    }

    static template = "field_service_tracking.tracking_route_template";
}

registry.category("actions").add("gps_tracking_route_map", GpsTrackingMap);

