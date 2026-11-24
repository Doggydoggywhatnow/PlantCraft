package com.plantcraft;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.LevelReader;
import net.minecraft.world.level.block.BonemealSource;
import net.minecraft.world.level.block.BonemealableBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.VegetationBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** A sapling: planted on soil, it eventually grows into a tree sized from the species' sourced height and width. */
public class TreeSaplingBlock extends VegetationBlock implements BonemealableBlock {
	private static final VoxelShape SHAPE = Shapes.box(0.1, 0.0, 0.1, 0.9, 0.8, 0.9);
	private final TreeGen.Spec spec;
	private final Block log;
	private final Block leaves;

	public TreeSaplingBlock(Properties properties, TreeGen.Spec spec, Block log, Block leaves) {
		super(properties);
		this.spec = spec;
		this.log = log;
		this.leaves = leaves;
	}

	@Override
	protected boolean isRandomlyTicking(BlockState state) {
		return true;
	}

	@Override
	protected void randomTick(BlockState state, ServerLevel level, BlockPos pos, RandomSource random) {
		if (level.getRawBrightness(pos, 0) >= 9 && random.nextInt(8) == 0) {
			TreeGen.grow(level, pos, spec, log, leaves);
		}
	}

	@Override
	protected boolean mayPlaceOn(BlockState below, BlockGetter level, BlockPos pos) {
		return below.is(BlockTags.SUPPORTS_VEGETATION);
	}

	@Override
	protected VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context) {
		return SHAPE;
	}

	@Override
	public boolean isValidBonemealTarget(LevelReader level, BlockPos pos, BlockState state, BonemealSource source) {
		return true;
	}

	@Override
	public boolean isBonemealSuccess(Level level, RandomSource random, BlockPos pos, BlockState state, BonemealSource source) {
		return random.nextFloat() < 0.45F;                                          // like vanilla saplings
	}

	@Override
	public void performBonemeal(ServerLevel level, RandomSource random, BlockPos pos, BlockState state, BonemealSource source) {
		TreeGen.grow(level, pos, spec, log, leaves);
	}
}
