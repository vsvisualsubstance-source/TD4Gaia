vec3 seedHash3(float s) {
	float x = fract(sin(s * 127.1 + 1.0) * 43758.5453123);
	float y = fract(sin(s * 269.5 + 3.0) * 24634.6345231);
	float z = fract(sin(s * 419.2 + 7.0) * 39215.3141592);
	return vec3(x, y, z);
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

	// Registry texture: row0=seedNorm, row1=countNorm, row2=alpha, row3=roomNorm
	float seedNorm = texelFetch(objTex, ivec2(int(id), 0), 0).r;
	float countNorm = texelFetch(objTex, ivec2(int(id), 1), 0).r;
	float alpha = texelFetch(objTex, ivec2(int(id), 2), 0).r;
	float roomNorm = texelFetch(objTex, ivec2(int(id), 3), 0).r;

	vec3 h = seedHash3(seedNorm * 97.0 + 0.0001);

	// Deterministic base position from the seed alone - each room owns an
	// angular sector, the seed places the inhabitant within it. Same seed
	// (same class, per Gaia's FNV-1a hash) always lands in the same spot;
	// this is the identity, not randomness.
	float sector = 6.28318530718 / 4.0;
	float angle = roomNorm * 6.28318530718 + (h.x - 0.5) * sector * 0.8;
	float radius = 2.8 + h.y * 0.6;
	float height = (h.z - 0.5) * 1.2;

	// Time only modulates on top of the seed-derived base - never replaces it.
	angle += uTime * 0.04;
	height += sin(uTime * 0.3 + seedNorm * 6.28318530718) * 0.08 * alpha;

	P[id] = vec3(radius * cos(angle), height, radius * sin(angle));

	vec3 seedColor = hsv2rgb(vec3(seedNorm, 0.55, 1.0));
	vec3 moodColor = vec3(uMoodR, uMoodG, uMoodB);
	vec3 col = mix(seedColor, moodColor, 0.3);
	col = clamp(col, 0.0, 1.0);
	Color[id] = vec4(col, 1.0);

	// Fade with the registry's appear/decay alpha - dissolve, never a snap.
	PointScale[id] = (0.35 + 0.9 * countNorm) * alpha;
}
