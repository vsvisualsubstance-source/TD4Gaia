// Cheap stable hash, same technique as soul_geo's per-point identity.
uint hash11(uint x) {
	x ^= x >> 16;
	x *= 0x7feb352du;
	x ^= x >> 15;
	x *= 0x846ca68bu;
	x ^= x >> 16;
	return x;
}
float hashFloat(uint seed) {
	return float(hash11(seed)) / 4294967295.0;
}

vec3 hsv2rgb(vec3 c) {
	vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
	vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
	return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main() {
	const uint id = TDIndex();
	if (id >= TDNumElements())
		return;

	// noteTex is an 80-row, 1-col texture: 16 r, 16 g, 16 b, 16
	// brightness, 16 roomNorm (script_plantnotes_tex's fixed channel
	// order). Slot index == point index (16 points, one per ring slot).
	float r = texelFetch(noteTex, ivec2(0, int(id)), 0).r;
	float g = texelFetch(noteTex, ivec2(0, int(id) + 16), 0).r;
	float b = texelFetch(noteTex, ivec2(0, int(id) + 32), 0).r;
	float bright = texelFetch(noteTex, ivec2(0, int(id) + 48), 0).r;
	float roomNorm = texelFetch(noteTex, ivec2(0, int(id) + 64), 0).r;

	// Base angle from the note's room (0-1 -> full circle), plus a small
	// stable per-slot jitter so several notes in the same room don't
	// stack exactly on top of each other.
	float jitter = (hashFloat(hash11(id * 7u + 3u)) - 0.5) * 0.9;
	float angle = roomNorm * 6.28318530718 + jitter;

	// Outside both the soul core (~1.0) and the zone light ring (2.0), but
	// still inside the camera frustum at this distance (~2.5 visible
	// half-extent at zones_geo's depth) - a 3.3+ radius was invisible,
	// off-frame entirely.
	float radiusJitter = hashFloat(hash11(id * 7u + 5u)) * 0.25;
	float radius = 2.15 + radiusJitter;
	float heightJitter = (hashFloat(hash11(id * 7u + 9u)) - 0.5) * 0.9;

	P[id] = vec3(radius * cos(angle), heightJitter, radius * sin(angle));

	// uTime has no other purpose here than making this shader time-varying
	// - with a purely static input (grid_base never changes) and the note
	// data arriving only via a sampler reference (not a wired input), TD's
	// cook analysis saw no reason to ever recompute this after the first
	// cook, so live plant_note updates never appeared (fixed color/scale
	// forever). Referencing time flags it to actually cook every frame
	// while demanded. Doubles as a faint twinkle so notes read as alive
	// even between real events.
	float twinkle = 0.92 + 0.08 * sin(uTime * 2.4 + float(id) * 1.7);

	vec3 col = vec3(r, g, b) * bright * twinkle;
	Color[id] = vec4(col, 1.0);
	PointScale[id] = 0.4 + 1.6 * bright;
}
