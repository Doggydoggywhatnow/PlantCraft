package com.plantcraft;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.VegetationBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.IntegerProperty;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** A herb: planted on soil, it moves through the growth stages from the plant's data file as random ticks pass. */
public class PlantBlock extends VegetationBlock {
	public static final IntegerProperty AGE = IntegerProperty.create("age", 0, 5);
	private static final VoxelShape SHAPE = Shapes.box(0.125, 0.0, 0.125, 0.875, 0.8, 0.875);
	private final int maxAge;

	public PlantBlock(Properties properties, int maxAge) {
		super(properties);
		this.maxAge = maxAge;
		registerDefaultState(stateDefinition.any().setValue(AGE, 0));
	}

	@Override
	protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder) {
		builder.add(AGE);
	}

	@Override
	protected boolean isRandomlyTicking(BlockState state) {
		return state.getValue(AGE) < maxAge;
	}

	@Override
	protected void randomTick(BlockState state, ServerLevel level, BlockPos pos, RandomSource random) {
		if (level.getRawBrightness(pos, 0) >= 9 && random.nextInt(5) == 0) {
			level.setBlock(pos, state.setValue(AGE, state.getValue(AGE) + 1), 2);
		}
	}

	@Override
	protected boolean mayPlaceOn(BlockState below, BlockGetter level, BlockPos pos) {
		return below.is(BlockTags.DIRT) || below.is(Blocks.FARMLAND);
	}

	@Override
	protected VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context) {
		return SHAPE;
	}
}
