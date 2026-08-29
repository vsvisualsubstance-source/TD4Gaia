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

	// lexTex: row0=seedNorm, row1=countNorm, row2=alpha (no room dimension)
	float seedNorm = texelFetch(lexTex, ivec2(int(id), 0), 0).r;
	float countNorm = texelFetch(lexTex, ivec2(int(id), 1), 0).r;
	float alpha = texelFetch(lexTex, ivec2(int(id), 2), 0).r;

	vec3 h = seedHash3(seedNorm * 131.0 + 0.0002);

	// Deterministic, diffuse scatter across a wide soft shell - same word
	// always lands in the same place, per the seed-identity rule.
	float angle = h.x * 6.28318530718;
	float radius = 3.5 + h.y * 2.0;
	float height = (h.z - 0.5) * 3.0;

	// Very slow shared drift and a gentle breathing pulse - dreamlike
	// stillness, motion only ever modulates the seed-derived base.
	angle += uTime * 0.008;
	float breathe = 0.5 + 0.5 * sin(uTime * 0.15 + seedNorm * 6.28318530718);

	P[id] = vec3(radius * cos(angle), height, radius * sin(angle));

	// Soft, desaturated, seed-hued color - less defined than daytime.
	vec3 col = hsv2rgb(vec3(seedNorm, 0.35, 0.85));
	col = clamp(col, 0.0, 1.0);
	Color[id] = vec4(col, 1.0);

	PointScale[id] = (0.5 + 0.5 * countNorm) * (0.6 + 0.4 * breathe) * alpha;
}
