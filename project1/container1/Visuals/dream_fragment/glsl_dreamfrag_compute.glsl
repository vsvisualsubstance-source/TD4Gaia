vec3 hsv2rgb(vec3 c) {
	vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
	vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
	return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

// Cheap stable hash, same technique used elsewhere in this project
// (registry/plantnotes) for jittering points without a real RNG.
float hashFloat(float seed) {
	return fract(sin(seed * 91.7) * 43758.5453);
}

void main() {
	const uint id = TDIndex();
	if (id >= TDNumElements())
		return;

	float n = float(TDNumElements());
	float t = float(id) / n;
	int shapeMode = int(uMod.y + 0.5);
	float scale = uMod.x;
	float angle = t * 6.28318530718 + uTime * 0.25;
	vec3 pos;

	if (shapeMode == 0) {
		// ring: steady orbit at fixed radius, gentle vertical bob
		float radius = 0.5 * scale;
		pos = vec3(radius * cos(angle), 0.15 * sin(uTime * 0.4 + t * 6.28318530718), radius * sin(angle));
	} else if (shapeMode == 1) {
		// spiral: radius grows with point index, winds outward
		float radius = (0.15 + 0.5 * t) * scale;
		float spiralAngle = angle * 3.0;
		pos = vec3(radius * cos(spiralAngle), (t - 0.5) * 0.6 * scale, radius * sin(spiralAngle));
	} else {
		// cluster: loose stable-jittered blob, no strict ordering
		float jr = hashFloat(t * 13.1);
		float ja = hashFloat(t * 27.7) * 6.28318530718;
		float radius = (0.25 + 0.25 * jr) * scale;
		pos = vec3(radius * cos(ja), (jr - 0.5) * 0.4 * scale, radius * sin(ja));
	}

	P[id] = pos;

	vec3 col = hsv2rgb(vec3(uHue, 0.55, 1.0));
	Color[id] = vec4(col, 1.0);
	PointScale[id] = (0.5 + 0.4 * scale);
}
