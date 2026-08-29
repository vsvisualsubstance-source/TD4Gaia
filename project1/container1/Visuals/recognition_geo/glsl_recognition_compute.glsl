vec3 hsv2rgb(vec3 c) {
	vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
	vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
	return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main() {
	const uint id = TDIndex();
	if (id >= TDNumElements())
		return;

	// personTex is a 16-row, 1-col texture: 4 r, 4 g, 4 b, 4 intensity
	// (script_recognition_tex's fixed channel order). Slot index == point
	// index == ROOMS index (4 fixed room markers, one per point).
	float r = texelFetch(personTex, ivec2(0, int(id)), 0).r;
	float g = texelFetch(personTex, ivec2(0, int(id) + 4), 0).r;
	float b = texelFetch(personTex, ivec2(0, int(id) + 8), 0).r;
	float intensity = texelFetch(personTex, ivec2(0, int(id) + 12), 0).r;

	// Fixed quadrant per room index (offset by 0.5 so slot 0 and the
	// last slot don't land on the same angle, unlike the shared
	// _roomNorm()*2pi formula used elsewhere).
	float angle = (float(id) + 0.5) / 4.0 * 6.28318530718;

	// Inner ring: closer to the soul core (~1.0) than the plant-note
	// outer ring (2.15-2.4), since recognized people read as figures
	// near the "self", not ambient events outside it.
	float radius = 1.65;
	P[id] = vec3(radius * cos(angle), 0.0, radius * sin(angle));

	// uTime forces this shader to actually re-cook every frame - a
	// purely static grid input plus sampler-only data would otherwise
	// get cached forever by TD's cook analysis (see plantnotes_geo).
	// Doubles as a slow pulse so an active marker reads as alive.
	float pulse = 0.85 + 0.15 * sin(uTime * 1.6 + float(id) * 2.1);

	vec3 col = vec3(r, g, b) * intensity * pulse;
	Color[id] = vec4(col, 1.0);
	PointScale[id] = 0.5 + 2.2 * intensity;
}
