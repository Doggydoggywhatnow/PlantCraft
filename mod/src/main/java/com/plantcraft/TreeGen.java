package com.plantcraft;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;

/** Builds a trunk and a rounded crown. Sizes are drawn from the species' sourced ranges (see tools/sample_sizes.py). */
final class TreeGen {
	private TreeGen() {}

	/** Sourced ranges in centimetres; wHi = 0 means no width data; tail > 0 means rare giants up to that height. */
	record Spec(double hLo, double hHi, double tail, double wLo, double wHi) {}

	static void grow(ServerLevel level, BlockPos base, Spec s, Block log, Block leaves) {
		RandomSource r = RandomSource.create(base.asLong() * 6364136223846793005L + level.getSeed());
		double u = r.nextDouble();
		double heightCm = s.hLo() + u * (s.hHi() - s.hLo());
		if (s.tail() > 0 && r.nextDouble() < 0.03) {
			heightCm = s.hHi() + u * (s.tail() - s.hHi());
		}
		int height = Math.max(3, (int) Math.ceil(heightCm / 100.0));           // 1 block = 1 m
		int radius;
		if (s.wHi() > 0) {
			double wu = 0.7 * u + 0.3 * r.nextDouble();                          // width follows height, partly
			radius = Math.max(2, (int) Math.round((s.wLo() + wu * (s.wHi() - s.wLo())) / 200.0));
		} else {
			radius = Math.max(2, height / 10);                                   // no width data: design choice
		}
		int trunk = Math.max(2, (int) Math.round(height * 0.6));
		int ry = Math.max(2, (height - trunk) / 2 + 1);
		int cy = trunk + (height - trunk) / 2;
		BlockState leafState = leaves.defaultBlockState();
		for (int dy = -ry; dy <= ry; dy++) {
			for (int dx = -radius; dx <= radius; dx++) {
				for (int dz = -radius; dz <= radius; dz++) {
					double d = (double) (dx * dx) / (radius * radius) + (double) (dy * dy) / (ry * ry) + (double) (dz * dz) / (radius * radius);
					BlockPos p = base.offset(dx, cy + dy, dz);
					BlockState at = level.getBlockState(p);
					if (d <= 1.0 && (at.isAir() || at.canBeReplaced())) {
						level.setBlock(p, leafState, 2);
					}
				}
			}
		}
		BlockState logState = log.defaultBlockState();
		for (int i = 0; i < trunk; i++) {
			level.setBlock(base.above(i), logState, 2);
		}
	}
}
