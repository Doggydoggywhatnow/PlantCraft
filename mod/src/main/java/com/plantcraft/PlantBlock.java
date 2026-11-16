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
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.IntegerProperty;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** A herb: planted on soil, it moves through the growth stages from the plant's data file as random ticks pass. */
public class PlantBlock extends VegetationBlock implements BonemealableBlock {
	public static final IntegerProperty AGE = IntegerProperty.create("age", 0, 5);
	private static final VoxelShape SHAPE = Shapes.box(0.125, 0.0, 0.125, 0.875, 0.8, 0.875);
	private final int maxAge;
	private final Block stem;            // non-null for plants taller than one block
	private final TreeGen.Spec spec;     // sourced height range for those plants

	public PlantBlock(Properties properties, int maxAge, Block stem, TreeGen.Spec spec) {
		super(properties);
		this.maxAge = maxAge;
		this.stem = stem;
		this.spec = spec;
		registerDefaultState(stateDefinition.any().setValue(AGE, 0));
	}

	@Override
	protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder) {
		builder.add(AGE);
	}

	@Override
	protected boolean isRandomlyTicking(BlockState state) {
		return state.getValue(AGE) < maxAge || stem != null;
	}

	@Override
	protected void randomTick(BlockState state, ServerLevel level, BlockPos pos, RandomSource random) {
		if (level.getRawBrightness(pos, 0) < 9) {
			return;
		}
		if (state.getValue(AGE) < maxAge && random.nextInt(5) == 0) {
			level.setBlock(pos, state.setValue(AGE, state.getValue(AGE) + 1), 2);
			state = level.getBlockState(pos);
		}
		if (stem != null && state.getValue(AGE) >= 1 && random.nextInt(4) == 0) {
			growTaller(level, pos, state);
		}
	}

	/** Moves the top block up one and leaves a stem behind, until the plant reaches its own sourced height. */
	private boolean growTaller(ServerLevel level, BlockPos pos, BlockState state) {
		BlockPos base = pos;
		while (level.getBlockState(base.below()).is(stem)) {
			base = base.below();
		}
		int height = pos.getY() - base.getY() + 1;
		if (height >= TreeGen.blocksTall(level, base, spec) || !level.getBlockState(pos.above()).isAir()) {
			return false;
		}
		level.setBlock(pos, stem.defaultBlockState(), 2);
		level.setBlock(pos.above(), state, 2);
		return true;
	}

	@Override
	protected boolean mayPlaceOn(BlockState below, BlockGetter level, BlockPos pos) {
		return below.is(BlockTags.DIRT) || below.is(Blocks.FARMLAND) || (stem != null && below.is(stem));
	}

	@Override
	protected VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context) {
		return SHAPE;
	}

	@Override
	public boolean isValidBonemealTarget(LevelReader level, BlockPos pos, BlockState state, BonemealSource source) {
		return state.getValue(AGE) < maxAge || stem != null;
	}

	@Override
	public boolean isBonemealSuccess(Level level, RandomSource random, BlockPos pos, BlockState state, BonemealSource source) {
		return true;
	}

	@Override
	public void performBonemeal(ServerLevel level, RandomSource random, BlockPos pos, BlockState state, BonemealSource source) {
		int age = Math.min(maxAge, state.getValue(AGE) + 1 + random.nextInt(2));   // one or two stages
		BlockState grown = state.setValue(AGE, age);
		level.setBlock(pos, grown, 2);
		if (stem != null && age >= 1) {
			growTaller(level, pos, grown);
		}
	}
}
